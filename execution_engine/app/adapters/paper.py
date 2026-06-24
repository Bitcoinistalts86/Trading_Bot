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

from ..conditional import is_triggered, triggered_order_type
from ..config import Settings
from ..models import CONDITIONAL_TYPES, Execution, Order, OrderType, Side

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
        # Resting conditional orders, keyed by client_order_id. In live trading
        # these rest server-side on Binance; in paper we simulate triggering.
        self._resting: dict[str, Order] = {}
        self._oco_siblings: dict[str, str] = {}  # cord -> sibling cord (cancel-other)
        self.on_conditional_fill = None          # async callback(Execution) when one fires

    async def get_mark_price(self, instrument: str) -> float:
        return self._last_price.get(instrument.upper(), 0.0)

    def set_mark_price(self, instrument: str, price: float) -> None:
        if price > 0:
            self._last_price[instrument.upper()] = price

    async def update_mark_price(self, instrument: str, price: float) -> list[Execution]:
        """Set price AND fire any resting conditional orders it triggers."""
        self.set_mark_price(instrument, price)
        return await self._evaluate_triggers(instrument, price)

    async def get_balances(self) -> dict[str, float]:
        return dict(self.balances)

    def open_orders(self) -> list[str]:
        return list(self._resting.keys())

    def _base_asset(self, instrument: str) -> str:
        inst = instrument.upper()
        return inst[:-len(self.quote_asset)] if inst.endswith(self.quote_asset) else inst

    async def place_order(self, order: Order, ref_price: float) -> Execution:
        # Conditional orders rest until their trigger fires.
        if order.order_type in CONDITIONAL_TYPES:
            self._resting[order.client_order_id] = order
            logger.info("[PAPER] resting %s %s @ stop %.4f",
                        order.order_type.value, order.instrument, order.stop_price or 0.0)
            return Execution(
                order_id=order.client_order_id, exchange=self.name, instrument=order.instrument,
                side=order.side, price=order.stop_price or ref_price, quantity=0.0,
                status="RESTING", correlation_id=order.correlation_id,
            )
        return self._fill(order, ref_price)

    def _fill(self, order: Order, ref_price: float) -> Execution:
        ref = ref_price or self._last_price.get(order.instrument.upper(), 0.0)
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

        logger.info("[PAPER] %s %s %s @ %.4f (fee %.4f)",
                    order.side.value, order.quantity, order.instrument, fill_price, fee)
        return Execution(
            order_id=order.client_order_id, exchange=self.name, instrument=order.instrument,
            side=order.side, price=fill_price, quantity=order.quantity, fees=fee,
            status="SIMULATED", correlation_id=order.correlation_id,
        )

    def register_oco(self, leg_a: Order, leg_b: Order) -> None:
        """Register two legs that cancel each other when one fires."""
        self._resting[leg_a.client_order_id] = leg_a
        self._resting[leg_b.client_order_id] = leg_b
        self._oco_siblings[leg_a.client_order_id] = leg_b.client_order_id
        self._oco_siblings[leg_b.client_order_id] = leg_a.client_order_id

    async def place_oco(self, order: Order, ref_price: float) -> list[Execution]:
        """Build a take-profit leg (at tp_price) + a stop leg (at stop_price)."""
        if not (order.tp_price and order.stop_price):
            raise ValueError("OCO requires tp_price and stop_price")
        tp_leg = order.model_copy(update={
            "client_order_id": f"{order.client_order_id}-tp",
            "order_type": OrderType.TAKE_PROFIT, "stop_price": order.tp_price,
        })
        stop_leg = order.model_copy(update={
            "client_order_id": f"{order.client_order_id}-sl",
            "order_type": OrderType.STOP_LIMIT if order.stop_limit_price else OrderType.STOP_LOSS,
            "stop_price": order.stop_price,
        })
        self.register_oco(tp_leg, stop_leg)
        logger.info("[PAPER] resting OCO %s tp=%.4f stop=%.4f",
                    order.instrument, order.tp_price, order.stop_price)
        return [
            Execution(order_id=leg.client_order_id, exchange=self.name, instrument=order.instrument,
                      side=order.side, price=leg.stop_price, quantity=0.0,
                      status="RESTING", correlation_id=order.correlation_id)
            for leg in (tp_leg, stop_leg)
        ]

    async def _evaluate_triggers(self, instrument: str, price: float) -> list[Execution]:
        fired: list[Execution] = []
        for cord, order in list(self._resting.items()):
            if order.instrument.upper() != instrument.upper():
                continue
            if is_triggered(order.side, order.order_type, order.stop_price, price):
                self._resting.pop(cord, None)
                # OCO: cancel the sibling leg.
                sibling = self._oco_siblings.pop(cord, None)
                if sibling:
                    self._resting.pop(sibling, None)
                    self._oco_siblings.pop(sibling, None)
                # Triggered order becomes MARKET or LIMIT.
                exec_price = order.stop_limit_price if triggered_order_type(order.order_type) == OrderType.LIMIT else price
                ex = self._fill(order, exec_price or price)
                ex.status = "TRIGGERED"
                fired.append(ex)
                if self.on_conditional_fill:
                    await self.on_conditional_fill(ex)
        return fired
