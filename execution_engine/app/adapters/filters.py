# execution_engine/app/adapters/filters.py
"""
Binance symbol filters.

Binance rejects any order whose quantity or price violates the symbol's filters
(`LOT_SIZE`, `PRICE_FILTER`, `NOTIONAL`/`MIN_NOTIONAL`). The unified engine sent
raw quantities, so any order that didn't happen to land on a valid step/tick was
doomed with a -1013 / -2010 error. This module parses those filters from
`GET /api/v3/exchangeInfo` and rounds orders onto the valid grid, using `Decimal`
throughout so we never introduce float drift right before signing.

Rounding policy:
  * quantity -> floored to `stepSize` (never round *up*: rounding up could exceed
    intended size or available balance).
  * price    -> nearest `tickSize` (LIMIT orders only).
  * notional -> if `quantity * ref_price < minNotional`, the order is rejected
    rather than silently bumped, because bumping changes the trade's intent.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP


def _decimals(step: Decimal) -> int:
    """Number of decimal places implied by a step/tick size (e.g. 0.00001 -> 5)."""
    exp = step.normalize().as_tuple().exponent
    return max(0, -exp)


def fmt(value: Decimal, decimals: int) -> str:
    """Plain decimal string (no scientific notation) for the signed payload."""
    return f"{value:.{decimals}f}"


@dataclass
class SymbolFilters:
    symbol: str
    step_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    tick_size: Decimal
    min_price: Decimal
    max_price: Decimal
    min_notional: Decimal

    @property
    def qty_decimals(self) -> int:
        return _decimals(self.step_size)

    @property
    def price_decimals(self) -> int:
        return _decimals(self.tick_size)

    @classmethod
    def from_symbol_info(cls, info: dict) -> "SymbolFilters":
        by_type = {flt["filterType"]: flt for flt in info.get("filters", [])}
        lot = by_type.get("LOT_SIZE", {})
        price = by_type.get("PRICE_FILTER", {})
        notional = by_type.get("NOTIONAL") or by_type.get("MIN_NOTIONAL") or {}
        return cls(
            symbol=info["symbol"],
            step_size=Decimal(lot.get("stepSize", "0.00000001")),
            min_qty=Decimal(lot.get("minQty", "0")),
            max_qty=Decimal(lot.get("maxQty", "1000000000")),
            tick_size=Decimal(price.get("tickSize", "0.00000001")),
            min_price=Decimal(price.get("minPrice", "0")),
            max_price=Decimal(price.get("maxPrice", "1000000000")),
            min_notional=Decimal(notional.get("minNotional", notional.get("notional", "0")) or "0"),
        )

    def round_quantity(self, qty) -> Decimal:
        q = Decimal(str(qty))
        if self.step_size > 0:
            # floor onto the step grid, then normalise the representation
            q = (q // self.step_size) * self.step_size
            q = q.quantize(self.step_size, rounding=ROUND_DOWN)
        return q

    def round_price(self, price) -> Decimal:
        p = Decimal(str(price))
        if self.tick_size > 0:
            ticks = (p / self.tick_size).quantize(Decimal(1), rounding=ROUND_HALF_UP)
            p = ticks * self.tick_size
            p = p.quantize(self.tick_size)
        if self.max_price > 0:
            p = min(p, self.max_price)
        return max(p, self.min_price)

    def validate(self, qty: Decimal, ref_price) -> str | None:
        """Return a rejection reason string, or None if the order is acceptable."""
        ref = Decimal(str(ref_price))
        if qty <= 0:
            return "ZERO_QUANTITY_AFTER_ROUNDING"
        if qty < self.min_qty:
            return f"BELOW_MIN_QTY:{fmt(self.min_qty, self.qty_decimals)}"
        if self.max_qty > 0 and qty > self.max_qty:
            return f"ABOVE_MAX_QTY:{fmt(self.max_qty, self.qty_decimals)}"
        if self.min_notional > 0 and qty * ref < self.min_notional:
            return f"BELOW_MIN_NOTIONAL:{self.min_notional}"
        return None
