# execution_engine/tests/test_conditional.py
"""Stop / take-profit / OCO orders: trigger logic + paper-mode resting/firing."""
import asyncio

import pytest

from execution_engine.app.conditional import is_triggered, triggered_order_type
from execution_engine.app.config import ExecutionMode, Settings
from execution_engine.app.adapters.paper import PaperAdapter
from execution_engine.app.models import Order, OrderType, Side


def _paper():
    s = Settings(mode=ExecutionMode.PAPER)
    a = PaperAdapter(s)
    a.set_mark_price("BTCUSDT", 65_000)
    return a


# --- pure trigger logic ----------------------------------------------------
def test_sell_stop_loss_triggers_on_the_way_down():
    assert is_triggered(Side.SELL, OrderType.STOP_LOSS, 60_000, 59_999)
    assert not is_triggered(Side.SELL, OrderType.STOP_LOSS, 60_000, 60_001)


def test_sell_take_profit_triggers_on_the_way_up():
    assert is_triggered(Side.SELL, OrderType.TAKE_PROFIT, 70_000, 70_001)
    assert not is_triggered(Side.SELL, OrderType.TAKE_PROFIT, 70_000, 69_999)


def test_buy_stop_triggers_on_the_way_up():
    assert is_triggered(Side.BUY, OrderType.STOP_LOSS, 66_000, 66_500)


def test_triggered_type_mapping():
    assert triggered_order_type(OrderType.STOP_LIMIT) == OrderType.LIMIT
    assert triggered_order_type(OrderType.STOP_LOSS) == OrderType.MARKET


# --- paper resting + firing ------------------------------------------------
def test_stop_loss_rests_then_fires_when_price_drops():
    a = _paper()
    order = Order(instrument="BTCUSDT", side=Side.SELL, quantity=0.01,
                  order_type=OrderType.STOP_LOSS, stop_price=60_000)

    async def run():
        ex = await a.place_order(order, 65_000)
        assert ex.status == "RESTING" and ex.quantity == 0.0
        assert a.open_orders() == [order.client_order_id]

        # Price above the stop -> nothing fires.
        assert await a.update_mark_price("BTCUSDT", 61_000) == []
        # Price crosses the stop -> it fires as a market fill.
        fired = await a.update_mark_price("BTCUSDT", 59_500)
        assert len(fired) == 1 and fired[0].status == "TRIGGERED" and fired[0].quantity == 0.01
        assert a.open_orders() == []  # no longer resting
    asyncio.run(run())


def test_oco_one_fill_cancels_the_other():
    a = _paper()
    order = Order(instrument="BTCUSDT", side=Side.SELL, quantity=0.01,
                  order_type=OrderType.OCO, tp_price=70_000, stop_price=60_000)

    async def run():
        execs = await a.place_oco(order, 65_000)
        assert len(execs) == 2 and all(e.status == "RESTING" for e in execs)
        assert len(a.open_orders()) == 2

        # Price rises to the take-profit -> TP leg fires, stop leg cancelled.
        fired = await a.update_mark_price("BTCUSDT", 70_500)
        assert len(fired) == 1
        assert a.open_orders() == []  # sibling cancelled
    asyncio.run(run())
