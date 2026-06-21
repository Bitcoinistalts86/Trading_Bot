# execution_engine/app/execution.py
"""
Order executor. This is the single, reconciled version of the execution logic
that was split (and duplicated) across the two legacy files.

Key change vs legacy: TWAP and VWAP no longer "simulate" by mutating a dict with
a hard-coded volume curve. They slice the parent order into child orders and
route each child through the *same* ExchangeAdapter used by immediate orders --
so a TWAP is real on testnet/live and simulated on paper, with identical code.
The kill-switch and risk gate are re-checked between every slice, so a HARD kill
aborts a long-running TWAP mid-flight.
"""
from __future__ import annotations

import asyncio
import logging

from .adapters.base import ExchangeAdapter
from .models import Execution, Order, OrderType, Side
from .risk import RiskManager

logger = logging.getLogger("execution_engine.executor")

# U-shaped intraday volume profile (more volume at the open/close of the window).
_VWAP_PROFILE = [0.15, 0.10, 0.08, 0.07, 0.05, 0.05, 0.07, 0.10, 0.15, 0.18]


class Executor:
    def __init__(self, adapter: ExchangeAdapter, risk: RiskManager, on_execution=None) -> None:
        self.adapter = adapter
        self.risk = risk
        self._on_execution = on_execution  # async callback(Execution) for pub/sub + audit

    async def _emit(self, ex: Execution) -> None:
        self.risk.on_fill(ex.instrument, ex.side, ex.quantity)
        if self._on_execution:
            await self._on_execution(ex)

    async def _fill_child(self, child: Order, ref_price: float) -> Execution:
        self.risk.register_open()
        try:
            ex = await self.adapter.place_order(child, ref_price)
            await self._emit(ex)
            return ex
        finally:
            self.risk.register_closed()

    async def execute(self, order: Order) -> list[Execution]:
        ref_price = await self.adapter.get_mark_price(order.instrument)
        if order.order_type in (OrderType.MARKET, OrderType.LIMIT):
            return [await self._fill_child(order, ref_price)]
        if order.order_type == OrderType.TWAP:
            return await self._execute_sliced(order, [1 / 10] * 10)
        if order.order_type == OrderType.VWAP:
            return await self._execute_sliced(order, _VWAP_PROFILE)
        logger.error("Unsupported order type: %s", order.order_type)
        return []

    async def _execute_sliced(self, order: Order, weights: list[float]) -> list[Execution]:
        duration = order.duration_seconds or 60
        interval = duration / len(weights)
        executions: list[Execution] = []
        logger.info("Starting %s for %s %s over %ss in %d slices",
                    order.order_type.value, order.quantity, order.instrument, duration, len(weights))

        for i, w in enumerate(weights):
            # Re-check the gate before each slice: a kill-switch or breached limit
            # aborts the remainder of a long-running algo order.
            ref_price = await self.adapter.get_mark_price(order.instrument)
            child = Order(
                instrument=order.instrument, side=order.side,
                quantity=order.quantity * w, price=None, order_type=OrderType.MARKET,
                user_id=order.user_id, correlation_id=order.correlation_id,
                strategy_id=order.strategy_id,
            )
            decision = await self.risk.check(child, ref_price)
            if not decision.approved:
                logger.warning("%s aborted at slice %d/%d: %s",
                               order.order_type.value, i + 1, len(weights), decision.reason)
                break
            executions.append(await self._fill_child(child, ref_price))
            if i < len(weights) - 1:
                await asyncio.sleep(interval)
        return executions
