# execution_engine/app/models.py
"""
Canonical data models for the execution engine.

These intentionally mirror `contracts/trading.proto` (Signal / Order / Execution)
so the REST layer, the Pub/Sub layer, and the exchange adapters all agree on a
single shape. The two legacy engines disagreed on field names (`TradeSignal` vs
`Signal`, `price` vs `price_target`); this module is the single source of truth.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    TWAP = "TWAP"
    VWAP = "VWAP"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


class Signal(BaseModel):
    """A trading signal produced by a strategy/model (proto: trading.Signal)."""
    strategy_id: str = "unknown"
    instrument: str
    side: Side
    price_target: Optional[float] = None
    quantity: float
    order_type: OrderType = OrderType.MARKET
    duration_seconds: Optional[int] = 60  # for TWAP/VWAP
    # Operational fields needed for kill-switch scoping + auditing.
    user_id: str = "system"
    correlation_id: Optional[str] = None

    def to_order(self) -> "Order":
        return Order(
            client_order_id=_new_id("cord"),
            instrument=self.instrument,
            side=self.side,
            quantity=self.quantity,
            price=self.price_target,
            order_type=self.order_type,
            duration_seconds=self.duration_seconds,
            user_id=self.user_id,
            correlation_id=self.correlation_id or _new_id("corr"),
            strategy_id=self.strategy_id,
        )


class Order(BaseModel):
    """An order to be routed to an exchange (proto: trading.Order)."""
    client_order_id: str = Field(default_factory=lambda: _new_id("cord"))
    instrument: str
    side: Side
    quantity: float
    price: Optional[float] = None  # required for LIMIT, optional for MARKET
    order_type: OrderType = OrderType.MARKET
    duration_seconds: Optional[int] = 60
    user_id: str = "system"
    correlation_id: str = Field(default_factory=lambda: _new_id("corr"))
    strategy_id: str = "unknown"

    def notional(self, ref_price: float) -> float:
        return self.quantity * (self.price or ref_price)


class Execution(BaseModel):
    """The result of (a slice of) an order hitting a venue (proto: trading.Execution)."""
    execution_id: str = Field(default_factory=lambda: _new_id("exec"))
    order_id: str
    exchange: str
    instrument: str
    side: Side
    price: float
    quantity: float
    fees: float = 0.0
    status: str = "FILLED"  # FILLED | PARTIALLY_FILLED | REJECTED | SIMULATED
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    correlation_id: Optional[str] = None
