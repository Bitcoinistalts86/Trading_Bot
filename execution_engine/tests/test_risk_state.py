# execution_engine/tests/test_risk_state.py
"""
Tests for durable risk state. The in-memory path runs always; the Redis path
runs against fakeredis when installed, proving both implementations behave the
same and that daily-loss state survives a "restart" (new RiskManager, same store).
"""
import asyncio

import pytest

from execution_engine.app.config import RiskLimits
from execution_engine.app.kill_switch import _InMemoryKillSwitch
from execution_engine.app.models import Order, Side
from execution_engine.app.risk import RiskManager
from execution_engine.app.risk_state import InMemoryRiskState, RedisRiskState

try:
    import fakeredis.aioredis as _fakeredis
    _HAS_FAKEREDIS = True
except ImportError:
    _HAS_FAKEREDIS = False


def _states():
    states = [InMemoryRiskState()]
    if _HAS_FAKEREDIS:
        states.append(RedisRiskState(_fakeredis.FakeRedis(decode_responses=True)))
    return states


def test_rate_limit_window_counts_and_expires():
    for state in _states():
        async def run():
            now = 1000.0
            for i in range(3):
                await state.add_order(now + i)
            assert await state.trim_and_count_orders(now + 3, 60) == 3
            # 61s later the window has slid past all three
            assert await state.trim_and_count_orders(now + 70, 60) == 0
        asyncio.run(run())


def test_daily_pnl_accumulates():
    for state in _states():
        async def run():
            assert await state.get_realized_pnl("20260101") == 0.0
            await state.add_realized_pnl("20260101", -100.0)
            await state.add_realized_pnl("20260101", -50.0)
            assert await state.get_realized_pnl("20260101") == pytest.approx(-150.0)
            # different day is independent
            assert await state.get_realized_pnl("20260102") == 0.0
        asyncio.run(run())


def test_rate_limit_enforced_by_risk_manager():
    limits = RiskLimits()
    limits.max_orders_per_minute = 2
    risk = RiskManager(limits, _InMemoryKillSwitch(), state=InMemoryRiskState())

    async def run():
        order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.001)
        assert (await risk.check(order, 65_000.0)).approved      # 1
        assert (await risk.check(order, 65_000.0)).approved      # 2
        third = await risk.check(order, 65_000.0)                # 3 -> blocked
        assert not third.approved and third.reason == "RATE_LIMIT_EXCEEDED"
    asyncio.run(run())


def test_daily_loss_survives_restart():
    """A shared state means a fresh RiskManager (post-crash) still sees the loss."""
    for state in _states():
        async def run():
            limits = RiskLimits()
            limits.max_daily_loss_usd = 500.0

            # Engine instance 1 records a big loss, then "crashes".
            r1 = RiskManager(limits, _InMemoryKillSwitch(), state=state)
            await r1.record_realized_pnl(-600.0)

            # Engine instance 2 boots with the SAME durable state.
            r2 = RiskManager(limits, _InMemoryKillSwitch(), state=state)
            order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.001)
            decision = await r2.check(order, 65_000.0)
            assert not decision.approved and decision.reason == "DAILY_LOSS_LIMIT"
        asyncio.run(run())
