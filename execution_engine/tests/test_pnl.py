# execution_engine/tests/test_pnl.py
"""Average-cost realized-PnL tracker + the loop that activates the daily-loss limit."""
import asyncio

import pytest

from execution_engine.app.config import RiskLimits
from execution_engine.app.kill_switch import _InMemoryKillSwitch
from execution_engine.app.models import Order, Side
from execution_engine.app.pnl import PnLTracker
from execution_engine.app.risk import RiskManager
from execution_engine.app.risk_state import InMemoryRiskState


def test_buy_then_sell_higher_is_profit():
    t = PnLTracker()
    assert t.record_fill("BTCUSDT", "BUY", 60_000, 1.0) == 0.0          # buy, no realize
    realized = t.record_fill("BTCUSDT", "SELL", 65_000, 1.0)
    assert realized == pytest.approx(5_000.0)                          # +5k


def test_buy_then_sell_lower_is_loss():
    t = PnLTracker()
    t.record_fill("ETHUSDT", "BUY", 3_400, 2.0)
    realized = t.record_fill("ETHUSDT", "SELL", 3_300, 2.0)
    assert realized == pytest.approx(-200.0)                          # -100 * 2


def test_average_cost_over_multiple_buys():
    t = PnLTracker()
    t.record_fill("BTCUSDT", "BUY", 60_000, 1.0)
    t.record_fill("BTCUSDT", "BUY", 70_000, 1.0)                       # avg cost = 65k
    qty, avg = t.position("BTCUSDT")
    assert qty == pytest.approx(2.0) and avg == pytest.approx(65_000.0)
    realized = t.record_fill("BTCUSDT", "SELL", 65_000, 1.0)
    assert realized == pytest.approx(0.0)                             # sold at avg cost


def test_fees_reduce_realized_pnl():
    t = PnLTracker()
    t.record_fill("BTCUSDT", "BUY", 60_000, 1.0)
    realized = t.record_fill("BTCUSDT", "SELL", 60_000, 1.0, fee=7.5)
    assert realized == pytest.approx(-7.5)                            # flat price, fee is the loss


def test_losing_fills_trip_daily_loss_limit():
    """The closed loop: realized losses feed the durable counter and the
    daily-loss stand-down fires -- the control that was previously inert."""
    limits = RiskLimits()
    limits.max_daily_loss_usd = 1_000.0
    risk = RiskManager(limits, _InMemoryKillSwitch(), state=InMemoryRiskState())
    tracker = PnLTracker()

    async def feed_loss():
        tracker.record_fill("BTCUSDT", "BUY", 60_000, 1.0)
        delta = tracker.record_fill("BTCUSDT", "SELL", 58_500, 1.0)   # -1,500 realized
        await risk.record_realized_pnl(delta)

    async def run():
        await feed_loss()
        order = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.001)
        decision = await risk.check(order, 60_000.0)
        assert not decision.approved and decision.reason == "DAILY_LOSS_LIMIT"

    asyncio.run(run())
