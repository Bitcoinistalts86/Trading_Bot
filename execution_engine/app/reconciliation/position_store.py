# execution_engine/app/reconciliation/position_store.py
"""
Authoritative position/balance state, reconciled from the exchange.

Before this, the engine *inferred* balances and positions locally from the fills
it thought happened. That drifts: partial fills, fees, manual trades, and missed
acks all desync local state from the exchange's truth. The user-data WebSocket
stream is the source of truth -- `outboundAccountPosition` carries authoritative
balances and `executionReport` carries order/fill lifecycle. This store applies
those events and is the single thing the engine reports from in testnet/live.

It is deliberately pure (no network) so it can be unit-tested with synthetic
event payloads.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# Common quote assets, longest-first so e.g. "FDUSD" is matched before "USD".
_QUOTES = ("FDUSD", "USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB")

# Order statuses that mean the order is no longer working.
_TERMINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}


@dataclass
class _Balance:
    free: float = 0.0
    locked: float = 0.0


@dataclass
class PositionStore:
    balances: dict[str, _Balance] = field(default_factory=dict)
    open_orders: dict[str, dict] = field(default_factory=dict)  # keyed by exchange orderId
    seeded: bool = False
    last_update_ms: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # --- seeding (from REST on startup) ------------------------------------
    def seed(self, balances: list[dict], open_orders: list[dict]) -> None:
        with self._lock:
            self.balances = {
                b["asset"]: _Balance(float(b.get("free", 0)), float(b.get("locked", 0)))
                for b in balances
            }
            self.open_orders = {str(o["orderId"]): self._norm_order(o) for o in open_orders}
            self.seeded = True
            self.last_update_ms = int(time.time() * 1000)

    # --- event application (from the WS stream) ----------------------------
    def apply_account_position(self, event: dict) -> None:
        """`outboundAccountPosition`: authoritative balance snapshot for changed assets."""
        with self._lock:
            for bal in event.get("B", []):
                self.balances[bal["a"]] = _Balance(float(bal["f"]), float(bal["l"]))
            self.last_update_ms = int(event.get("E", time.time() * 1000))

    def apply_execution_report(self, event: dict) -> dict | None:
        """
        `executionReport`: order lifecycle. Returns a fill dict when this report
        represents a non-zero fill (for the audit ledger), else None.
        """
        with self._lock:
            order_id = str(event.get("i"))
            status = event.get("X")
            if status in _TERMINAL:
                self.open_orders.pop(order_id, None)
            else:  # NEW, PARTIALLY_FILLED, PENDING_NEW, etc. -> still working
                self.open_orders[order_id] = {
                    "orderId": order_id,
                    "clientOrderId": event.get("c"),
                    "symbol": event.get("s"),
                    "side": event.get("S"),
                    "status": status,
                    "orig_qty": float(event.get("q", 0) or 0),
                    "filled_qty": float(event.get("z", 0) or 0),
                }
            self.last_update_ms = int(event.get("E", time.time() * 1000))

            last_fill = float(event.get("l", 0) or 0)
            if last_fill > 0:
                return {
                    "order_id": order_id,
                    "symbol": event.get("s"),
                    "side": event.get("S"),
                    "qty": last_fill,
                    "price": float(event.get("L", 0) or 0),  # last filled price
                    "fee": float(event.get("n", 0) or 0),
                    "fee_asset": event.get("N"),
                }
            return None

    # --- reads --------------------------------------------------------------
    def free_balances(self) -> dict[str, float]:
        with self._lock:
            return {a: b.free for a, b in self.balances.items() if b.free or b.locked}

    def open_order_count(self) -> int:
        with self._lock:
            return len(self.open_orders)

    def position_for(self, symbol: str) -> float:
        """Spot position in a symbol = free balance of its base asset."""
        base = self._base_asset(symbol)
        with self._lock:
            bal = self.balances.get(base)
            return bal.free if bal else 0.0

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "seeded": self.seeded,
                "last_update_ms": self.last_update_ms,
                "open_orders": list(self.open_orders.values()),
                "balances": {a: {"free": b.free, "locked": b.locked} for a, b in self.balances.items()},
            }

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _base_asset(symbol: str) -> str:
        s = symbol.upper()
        for q in _QUOTES:
            if s.endswith(q) and len(s) > len(q):
                return s[: -len(q)]
        return s

    @staticmethod
    def _norm_order(o: dict) -> dict:
        return {
            "orderId": str(o["orderId"]),
            "clientOrderId": o.get("clientOrderId"),
            "symbol": o.get("symbol"),
            "side": o.get("side"),
            "status": o.get("status"),
            "orig_qty": float(o.get("origQty", 0) or 0),
            "filled_qty": float(o.get("executedQty", 0) or 0),
        }
