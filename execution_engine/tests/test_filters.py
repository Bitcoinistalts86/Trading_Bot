# execution_engine/tests/test_filters.py
"""Offline tests for Binance symbol-filter rounding/validation (no network)."""
from decimal import Decimal

from execution_engine.app.adapters.filters import SymbolFilters

# Representative BTCUSDT-style filter blob (shape matches exchangeInfo).
BTCUSDT_INFO = {
    "symbol": "BTCUSDT",
    "filters": [
        {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000.00", "tickSize": "0.01"},
        {"filterType": "LOT_SIZE", "minQty": "0.00001", "maxQty": "9000.0", "stepSize": "0.00001"},
        {"filterType": "NOTIONAL", "minNotional": "5.0"},
    ],
}


def _filters():
    return SymbolFilters.from_symbol_info(BTCUSDT_INFO)


def test_parses_filters():
    f = _filters()
    assert f.symbol == "BTCUSDT"
    assert f.step_size == Decimal("0.00001")
    assert f.tick_size == Decimal("0.01")
    assert f.min_notional == Decimal("5.0")
    assert f.qty_decimals == 5
    assert f.price_decimals == 2


def test_quantity_floored_to_step():
    f = _filters()
    # 0.123456789 -> floored to 0.00001 grid -> 0.12345 (never rounds up)
    assert f.round_quantity(0.123456789) == Decimal("0.12345")
    assert f.round_quantity(0.000019) == Decimal("0.00001")


def test_price_rounded_to_tick():
    f = _filters()
    assert f.round_price(65000.017) == Decimal("65000.02")
    assert f.round_price(65000.014) == Decimal("65000.01")


def test_min_notional_rejection():
    f = _filters()
    # 0.00001 BTC * 65000 = 0.65 USDT, well under the 5.0 minNotional
    qty = f.round_quantity(0.00001)
    assert f.validate(qty, Decimal("65000")) == "BELOW_MIN_NOTIONAL:5.0"


def test_min_qty_rejection_after_rounding_to_zero():
    f = _filters()
    qty = f.round_quantity(0.000001)  # below step -> floors to 0
    assert f.validate(qty, Decimal("65000")) == "ZERO_QUANTITY_AFTER_ROUNDING"


def test_valid_order_passes():
    f = _filters()
    qty = f.round_quantity(0.01)  # 0.01 BTC ~ 650 USDT
    assert f.validate(qty, Decimal("65000")) is None
    assert str(qty) == "0.01000"  # quantized to step precision
