# execution_engine/app/pnl.py
"""
Realized-PnL tracker (average-cost basis).

The durable daily-loss limit (in RiskManager) reads a counter that, until now,
nothing populated -- so the stand-down never tripped. This computes realized PnL
from fills and feeds that counter, activating the limit.

Method: average cost basis (the standard pragmatic choice for a risk control --
simpler and less stateful than FIFO lot matching):
  * BUY  -> grows the position; updates the average cost; realizes nothing.
  * SELL -> realizes qty * (sell_price - avg_cost), minus fees; shrinks position.

Spot, long-only. Fees are treated as a quote-denominated cost subtracted from
realized PnL; normalizing fees paid in a third asset (e.g. BNB) to quote is a
later refinement and only makes the limit slightly conservative.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

_QUOTES = ("FDUSD", "USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB")


def _base_asset(symbol: str) -> str:
    s = symbol.upper()
    for q in _QUOTES:
        if s.endswith(q) and len(s) > len(q):
            return s[: -len(q)]
    return s


@dataclass
class _Lot:
    qty: float = 0.0
    avg_cost: float = 0.0  # quote per unit of base


@dataclass
class PnLTracker:
    lots: dict[str, _Lot] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_fill(self, symbol: str, side: str, price: float, qty: float, fee: float = 0.0) -> float:
        """Apply a fill; return the realized-PnL delta (positive = gain)."""
        if qty <= 0 or price <= 0:
            return 0.0
        base = _base_asset(symbol)
        with self._lock:
            lot = self.lots.setdefault(base, _Lot())
            side = side.upper()

            if side == "BUY":
                total_cost = lot.qty * lot.avg_cost + qty * price + fee
                lot.qty += qty
                lot.avg_cost = total_cost / lot.qty if lot.qty > 0 else 0.0
                return 0.0  # buys don't realize PnL (fee folded into cost basis)

            # SELL
            sell_qty = min(qty, lot.qty) if lot.qty > 0 else qty
            realized = sell_qty * (price - lot.avg_cost) - fee
            lot.qty = max(0.0, lot.qty - qty)
            if lot.qty <= 0:
                lot.avg_cost = 0.0  # flat -> reset basis
            return realized

    def position(self, symbol: str) -> tuple[float, float]:
        with self._lock:
            lot = self.lots.get(_base_asset(symbol))
            return (lot.qty, lot.avg_cost) if lot else (0.0, 0.0)
