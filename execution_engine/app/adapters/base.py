# execution_engine/app/adapters/base.py
"""
Exchange adapter interface.

This is the seam the two legacy engines were missing. Both of them hard-coded
"execution" as mutating an in-memory dict. By routing every fill through an
`ExchangeAdapter`, the *same* executor/risk/TWAP code drives a simulator in
paper mode and a real signed exchange API in testnet/live mode -- with no
branching in the business logic.
"""
from __future__ import annotations

import abc

from ..models import Execution, Order


class ExchangeAdapter(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def get_mark_price(self, instrument: str) -> float:
        """Return the current reference price for an instrument."""

    @abc.abstractmethod
    async def get_balances(self) -> dict[str, float]:
        """Return free balances keyed by asset (e.g. {'USDT': 100.0, 'BTC': 0.1})."""

    @abc.abstractmethod
    async def place_order(self, order: Order, ref_price: float) -> Execution:
        """Submit a single (already risk-checked) order and return its Execution."""

    async def place_oco(self, order: Order, ref_price: float) -> list[Execution]:
        """Place a one-cancels-other pair (take-profit + stop). Override per venue."""
        raise NotImplementedError("OCO not supported by this adapter")

    async def close(self) -> None:
        """Release any network resources. Override if needed."""
        return None
