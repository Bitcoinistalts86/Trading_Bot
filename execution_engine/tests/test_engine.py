# execution_engine/tests/test_engine.py
"""
Tests for the unified execution engine. These run fully offline (paper adapter,
in-memory kill-switch) -- no GCP, no Redis, no network.
"""
import asyncio

import pytest

from execution_engine.app.config import ExecutionMode, RiskLimits, Settings
from execution_engine.app.adapters.paper import PaperAdapter
from execution_engine.app.execution import Executor
from execution_engine.app.kill_switch import KillSwitchLevel, _InMemoryKillSwitch
from execution_engine.app.models import Order, OrderType, Side
from execution_engine.app.risk import RiskManager


def _settings(**over):
    s = Settings(mode=ExecutionMode.PAPER)
    s.paper_starting_usd = over.get("usd", 100_000.0)
    s.limits = over.get("limits", RiskLimits())
    return s


def _ctx(limits=None, usd=100_000.0):
    settings = _settings(usd=usd, limits=limits or RiskLimits())
    adapter = PaperAdapter(settings)
    adapter.set_mark_price("BTCUSDT", 65_000.0)
    ks = _InMemoryKillSwitch()
    risk = RiskManager(settings.limits, ks)
    executor = Executor(adapter, risk)
    return adapter, ks, risk, executor


def test_paper_buy_updates_balances():
    adapter, _, _, executor = _ctx()
    order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.01, order_type=OrderType.MARKET)
    execs = asyncio.run(executor.execute(order))
    assert len(execs) == 1 and execs[0].quantity == 0.01
    balances = asyncio.run(adapter.get_balances())
    assert balances["BTC"] == pytest.approx(0.01)
    assert balances["USDT"] < 100_000.0  # paid notional + fee


def test_order_notional_cap_blocks_fat_finger():
    limits = RiskLimits()
    limits.max_order_notional_usd = 100.0  # tiny cap
    _, _, risk, _ = _ctx(limits=limits)
    order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=1.0)  # ~65k notional
    decision = asyncio.run(risk.check(order, 65_000.0))
    assert not decision.approved and decision.reason == "ORDER_NOTIONAL_EXCEEDED"


def test_hard_kill_blocks_orders():
    _, ks, risk, _ = _ctx()
    asyncio.run(ks.set_global_level(KillSwitchLevel.HARD))
    order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.001)
    decision = asyncio.run(risk.check(order, 65_000.0))
    assert not decision.approved and decision.reason == "HARD_KILL_ACTIVE"


def test_twap_slices_into_children():
    adapter, _, _, executor = _ctx()
    order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.10,
                  order_type=OrderType.TWAP, duration_seconds=0)  # 0s => no real sleep
    execs = asyncio.run(executor.execute(order))
    assert len(execs) == 10
    assert sum(e.quantity for e in execs) == pytest.approx(0.10)


def test_twap_aborts_on_kill_midflight():
    adapter, ks, risk, executor = _ctx()

    # Trip the kill-switch after the first slice fills.
    original = adapter.place_order
    state = {"n": 0}

    async def hooked(o, ref):
        state["n"] += 1
        if state["n"] == 1:
            await ks.set_global_level(KillSwitchLevel.HARD)
        return await original(o, ref)

    adapter.place_order = hooked
    order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.10,
                  order_type=OrderType.TWAP, duration_seconds=0)
    execs = asyncio.run(executor.execute(order))
    assert len(execs) == 1  # aborted before slice 2
