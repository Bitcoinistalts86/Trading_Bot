# execution_engine/app/conditional.py
"""
Conditional-order trigger logic (stop-loss / take-profit).

Pure functions, so the trigger semantics are unit-tested without any adapter or
network. Trigger direction is derived from (side, type), matching Binance's
convention:

  SELL + STOP_LOSS      -> fires when price falls to/through stop  (protect a long)
  SELL + TAKE_PROFIT    -> fires when price rises to/through stop  (bank a gain)
  BUY  + STOP_LOSS      -> fires when price rises to/through stop  (cover a short / breakout)
  BUY  + TAKE_PROFIT    -> fires when price falls to/through stop
"""
from __future__ import annotations

from .models import OrderType, Side

_STOP_TYPES = {OrderType.STOP_LOSS, OrderType.STOP_LIMIT}
_TP_TYPES = {OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT}


def is_triggered(side: Side, order_type: OrderType, stop_price: float, price: float) -> bool:
    """True if a conditional order with this trigger fires at `price`."""
    if stop_price is None or price <= 0:
        return False
    sell = side == Side.SELL
    if order_type in _STOP_TYPES:
        # stop-loss: sell triggers on the way down, buy on the way up
        return price <= stop_price if sell else price >= stop_price
    if order_type in _TP_TYPES:
        # take-profit: sell triggers on the way up, buy on the way down
        return price >= stop_price if sell else price <= stop_price
    return False


def triggered_order_type(order_type: OrderType) -> OrderType:
    """The order type a conditional becomes once it triggers."""
    if order_type in (OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT_LIMIT):
        return OrderType.LIMIT
    return OrderType.MARKET
