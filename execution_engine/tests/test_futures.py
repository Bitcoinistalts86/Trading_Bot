# execution_engine/tests/test_futures.py
"""Futures adapter: order-type mapping, param building, leverage clamp (offline)."""
import os

from execution_engine.app.config import ExecutionMode, Settings, load_settings
from execution_engine.app.adapters.binance_futures import (
    FuturesBinanceAdapter, futures_order_type, _BASE_URLS,
)
from execution_engine.app.models import Order, OrderType, Side


def _adapter():
    s = Settings(mode=ExecutionMode.TESTNET)
    s.binance_api_key = "k"
    s.binance_api_secret = "s"
    return FuturesBinanceAdapter(s)


def test_order_type_mapping():
    assert futures_order_type(OrderType.MARKET) == "MARKET"
    assert futures_order_type(OrderType.LIMIT) == "LIMIT"
    assert futures_order_type(OrderType.STOP_LOSS) == "STOP_MARKET"
    assert futures_order_type(OrderType.STOP_LIMIT) == "STOP"
    assert futures_order_type(OrderType.TAKE_PROFIT) == "TAKE_PROFIT_MARKET"
    assert futures_order_type(OrderType.TAKE_PROFIT_LIMIT) == "TAKE_PROFIT"


def test_base_urls_testnet_vs_live():
    assert "testnet.binancefuture.com" in _BASE_URLS[ExecutionMode.TESTNET]
    assert "fapi.binance.com" in _BASE_URLS[ExecutionMode.LIVE]


def test_market_params_have_no_price_or_stop():
    a = _adapter()
    o = Order(instrument="BTCUSDT", side=Side.BUY, quantity=0.01, order_type=OrderType.MARKET)
    p = a.build_order_params(o, "0.010", None, None)
    assert p["type"] == "MARKET" and "price" not in p and "stopPrice" not in p
    assert p["side"] == "BUY" and p["quantity"] == "0.010"


def test_limit_params_carry_price_and_tif():
    a = _adapter()
    o = Order(instrument="BTCUSDT", side=Side.SELL, quantity=0.01, order_type=OrderType.LIMIT, price=70000)
    p = a.build_order_params(o, "0.010", "70000.0", None)
    assert p["type"] == "LIMIT" and p["price"] == "70000.0" and p["timeInForce"] == "GTC"


def test_stop_limit_params_carry_price_and_stop():
    a = _adapter()
    o = Order(instrument="BTCUSDT", side=Side.SELL, quantity=0.01, order_type=OrderType.STOP_LIMIT,
              stop_price=60000, stop_limit_price=59900)
    p = a.build_order_params(o, "0.010", "59900.0", "60000.0")
    assert p["type"] == "STOP" and p["price"] == "59900.0" and p["stopPrice"] == "60000.0"


def test_stop_market_params_carry_only_stop():
    a = _adapter()
    o = Order(instrument="BTCUSDT", side=Side.SELL, quantity=0.01, order_type=OrderType.STOP_LOSS,
              stop_price=60000)
    p = a.build_order_params(o, "0.010", None, "60000.0")
    assert p["type"] == "STOP_MARKET" and p["stopPrice"] == "60000.0" and "price" not in p


def test_leverage_clamped_to_risk_cap(monkeypatch):
    monkeypatch.setenv("EXCHANGE", "binance-futures")
    monkeypatch.setenv("FUTURES_LEVERAGE", "25")
    monkeypatch.setenv("RISK_MAX_LEVERAGE", "5")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    s = load_settings()
    assert s.is_futures and s.futures_leverage == 5  # clamped down from 25
