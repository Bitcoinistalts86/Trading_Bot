# execution_engine/app/adapters/paper.py
"""
Paper-trading adapter: the consolidated, honest version of the in-memory
simulation that used to live in `execution_engine/main.py`.

Differences from the legacy sim:
  * Models slippage and taker fees, so simulated PnL is not free money.
  * Tracks balances per asset and derives positions, instead of a hard-coded
    {"USD", "ETH"} pair.
  * Implements the same `ExchangeAdapter` interface as the real Binance adapter,
    so it is a drop-in and the executor code never branches on mode.
"""
from __future__ import annotations

import logging

from ..config import Settings
from ..models import Execution, Order, Side

logger = logging.getLogger("execution_engine.adapter.paper")

# Minimal mark-price seeds for offline/paper use. Real price comes from the
# market-data pipeline in a wired deployment; these are only fallbacks.
_SEED_PRICES = {"BTCUSDT": 65_000.0, "ETHUSDT": 3_400.0, "SOLUSDT": 150.0}


class PaperAdapter:
    name = "paper"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.quote_asset = "USDT"
        self.balances: dict[str, float] = {self.quote_asset: settings.paper_starting_usd}
        self._last_price: dict[str, float] = dict(_SEED_PRICES)

    async def get_mark_price(self, instrument: str) -> float:
        return self._last_price.get(instrument.upper(), 0.0)

    def set_mark_price(self, instrument: str, price: float) -> None:
        if price > 0:
            self._last_price[instrument.upper()] = price

    async def get_balances(self) -> dict[str, float]:
        return dict(self.balances)

    def _base_asset(self, instrument: str) -> str:
        inst = instrument.upper()
        return inst[:-len(self.quote_asset)] if inst.endswith(self.quote_asset) else inst

    async def place_order(self, order: Order, ref_price: float) -> Execution:
        ref = ref_price or await self.get_mark_price(order.instrument)
        slip = self.settings.paper_slippage_bps / 10_000.0
        # Buyers pay up, sellers receive less -- slippage always hurts.
        fill_price = ref * (1 + slip) if order.side == Side.BUY else ref * (1 - slip)
        fee = abs(order.quantity * fill_price) * (self.settings.taker_fee_bps / 10_000.0)

        base = self._base_asset(order.instrument)
        self.balances.setdefault(base, 0.0)
        notional = order.quantity * fill_price

        if order.side == Side.BUY:
            self.balances[self.quote_asset] -= notional + fee
            self.balances[base] += order.quantity
        else:
            self.balances[self.quote_asset] += notional - fee
            self.balances[base] -= order.quantity

        logger.info(
            "[PAPER] %s %s %s @ %.4f (fee %.4f)",
            order.side.value, order.quantity, order.instrument, fill_price, fee,
        )
        return Execution(
            order_id=order.client_order_id,
            exchange=self.name,
            instrument=order.instrument,
            side=order.side,
            price=fill_price,
            quantity=order.quantity,
            fees=fee,
            status="SIMULATED",
            correlation_id=order.correlation_id,
        )
