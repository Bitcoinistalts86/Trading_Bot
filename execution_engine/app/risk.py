# execution_engine/app/risk.py
"""
Pre-trade risk manager.

The legacy engines' entire risk logic was: "do you have enough balance?" plus a
boolean kill-switch. That is nowhere near enough to point at a funded account.
This manager enforces the limits you actually need before an order can reach a
venue, evaluated in cheap-to-expensive order so the common rejection paths are
fast:

  1. Kill-switch (hard then soft)        -- halt / reject-new
  2. Order notional cap                  -- no fat-finger single orders
  3. Per-minute order rate limit         -- runaway-loop protection
  4. Open-order cap                       -- bounded in-flight exposure
  5. Projected position notional cap      -- bounded directional exposure
  6. Daily realized-loss cap              -- automatic stand-down after losses
  7. Slippage guard (price vs mark)       -- reject orders priced through limits

Every rejection returns a machine-readable reason so it can be logged to the
immutable audit ledger.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from .config import RiskLimits
from .models import Order, Side


@dataclass
class RiskDecision:
    approved: bool
    reason: str = "OK"


class RiskManager:
    def __init__(self, limits: RiskLimits, kill_switch) -> None:
        self.limits = limits
        self.kill_switch = kill_switch
        self._order_times: deque[float] = deque(maxlen=10_000)
        self._open_orders = 0
        self._position_qty: dict[str, float] = {}   # signed base-asset qty per instrument
        self._daily_realized_pnl = 0.0
        self._pnl_day = time.gmtime().tm_yday

    # --- state updates (called by the executor on fills) --------------------
    def register_open(self) -> None:
        self._open_orders += 1

    def register_closed(self) -> None:
        self._open_orders = max(0, self._open_orders - 1)

    def on_fill(self, instrument: str, side: Side, qty: float, realized_pnl: float = 0.0) -> None:
        signed = qty if side == Side.BUY else -qty
        self._position_qty[instrument.upper()] = self._position_qty.get(instrument.upper(), 0.0) + signed
        self._roll_day()
        self._daily_realized_pnl += realized_pnl

    def _roll_day(self) -> None:
        today = time.gmtime().tm_yday
        if today != self._pnl_day:
            self._pnl_day = today
            self._daily_realized_pnl = 0.0

    # --- the gate -----------------------------------------------------------
    async def check(self, order: Order, ref_price: float) -> RiskDecision:
        # 1. kill-switch
        if await self.kill_switch.is_hard_kill_active(order.user_id):
            return RiskDecision(False, "HARD_KILL_ACTIVE")
        if await self.kill_switch.is_soft_kill_active(order.user_id):
            return RiskDecision(False, "SOFT_KILL_ACTIVE")

        price = order.price or ref_price
        if price <= 0:
            return RiskDecision(False, "NO_REFERENCE_PRICE")
        notional = order.quantity * price

        # 2. order notional cap
        if notional > self.limits.max_order_notional_usd:
            return RiskDecision(False, "ORDER_NOTIONAL_EXCEEDED")

        # 3. rate limit
        now = time.time()
        while self._order_times and now - self._order_times[0] > 60:
            self._order_times.popleft()
        if len(self._order_times) >= self.limits.max_orders_per_minute:
            return RiskDecision(False, "RATE_LIMIT_EXCEEDED")

        # 4. open-order cap
        if self._open_orders >= self.limits.max_open_orders:
            return RiskDecision(False, "MAX_OPEN_ORDERS")

        # 5. projected position notional
        signed = order.quantity if order.side == Side.BUY else -order.quantity
        projected = abs(self._position_qty.get(order.instrument.upper(), 0.0) + signed) * price
        if projected > self.limits.max_position_notional_usd:
            return RiskDecision(False, "POSITION_NOTIONAL_EXCEEDED")

        # 6. daily loss cap
        self._roll_day()
        if self._daily_realized_pnl <= -abs(self.limits.max_daily_loss_usd):
            return RiskDecision(False, "DAILY_LOSS_LIMIT")

        # 7. slippage guard (only meaningful for priced/limit orders)
        if order.price and ref_price > 0:
            slip_bps = abs(order.price - ref_price) / ref_price * 10_000
            if slip_bps > self.limits.max_slippage_bps:
                return RiskDecision(False, "SLIPPAGE_LIMIT")

        self._order_times.append(now)
        return RiskDecision(True, "OK")

    def snapshot(self) -> dict:
        return {
            "open_orders": self._open_orders,
            "positions": self._position_qty,
            "daily_realized_pnl": round(self._daily_realized_pnl, 2),
            "limits": vars(self.limits),
        }
