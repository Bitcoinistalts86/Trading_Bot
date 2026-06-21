# execution_engine/tests/test_reconciliation.py
"""Offline tests for the PositionStore (synthetic exchange events, no network)."""
from execution_engine.app.reconciliation.position_store import PositionStore
from execution_engine.app.config import RiskLimits
from execution_engine.app.kill_switch import _InMemoryKillSwitch
from execution_engine.app.models import Order, Side
from execution_engine.app.risk import RiskManager
import asyncio


def test_seed_sets_balances_and_open_orders():
    s = PositionStore()
    s.seed(
        balances=[{"asset": "USDT", "free": "1000", "locked": "0"},
                  {"asset": "BTC", "free": "0.5", "locked": "0.1"}],
        open_orders=[{"orderId": 1, "symbol": "BTCUSDT", "side": "BUY",
                      "status": "NEW", "origQty": "0.2", "executedQty": "0"}],
    )
    assert s.seeded
    assert s.free_balances()["BTC"] == 0.5
    assert s.open_order_count() == 1
    assert s.position_for("BTCUSDT") == 0.5  # base-asset free balance


def test_account_position_event_updates_balances():
    s = PositionStore()
    s.seed([{"asset": "USDT", "free": "1000", "locked": "0"}], [])
    s.apply_account_position({
        "e": "outboundAccountPosition", "E": 123,
        "B": [{"a": "USDT", "f": "900.0", "l": "0"}, {"a": "BTC", "f": "0.0015", "l": "0"}],
    })
    assert s.free_balances()["USDT"] == 900.0
    assert s.free_balances()["BTC"] == 0.0015


def test_execution_report_lifecycle_and_fill():
    s = PositionStore()
    s.seed([], [])
    # NEW -> becomes a working open order
    s.apply_execution_report({"e": "executionReport", "i": 42, "s": "BTCUSDT", "S": "BUY",
                              "X": "NEW", "q": "0.01", "z": "0", "l": "0"})
    assert s.open_order_count() == 1

    # PARTIALLY_FILLED with a fill -> returns a fill dict, stays open
    fill = s.apply_execution_report({"e": "executionReport", "i": 42, "s": "BTCUSDT", "S": "BUY",
                                     "X": "PARTIALLY_FILLED", "q": "0.01", "z": "0.004",
                                     "l": "0.004", "L": "65000", "n": "0.0001", "N": "BNB"})
    assert fill is not None and fill["qty"] == 0.004 and fill["price"] == 65000.0
    assert s.open_order_count() == 1

    # FILLED -> terminal, removed from open orders
    s.apply_execution_report({"e": "executionReport", "i": 42, "s": "BTCUSDT", "S": "BUY",
                              "X": "FILLED", "q": "0.01", "z": "0.01", "l": "0.006", "L": "65010"})
    assert s.open_order_count() == 0


def test_risk_reads_authoritative_state_when_store_bound():
    limits = RiskLimits()
    limits.max_open_orders = 1
    risk = RiskManager(limits, _InMemoryKillSwitch())

    store = PositionStore()
    store.seed([{"asset": "USDT", "free": "100000", "locked": "0"}],
               open_orders=[{"orderId": 7, "symbol": "ETHUSDT", "side": "BUY",
                             "status": "NEW", "origQty": "1", "executedQty": "0"}])
    risk.bind_store(store)

    # The store already shows 1 open order == the cap, so a new order is blocked,
    # even though the local counter the risk manager keeps is still 0.
    order = Order(instrument="ETHUSDT", side=Side.BUY, quantity=0.001)
    decision = asyncio.run(risk.check(order, 3400.0))
    assert not decision.approved and decision.reason == "MAX_OPEN_ORDERS"
