# execution_engine/app/adapters/__init__.py
"""Adapter factory: pick the venue adapter for the configured execution mode."""
from __future__ import annotations

import logging

from ..config import ExecutionMode, Settings
from .base import ExchangeAdapter
from .paper import PaperAdapter

logger = logging.getLogger("execution_engine.adapters")


async def build_adapter(settings: Settings) -> ExchangeAdapter:
    if settings.mode == ExecutionMode.PAPER:
        return PaperAdapter(settings)

    # TESTNET / LIVE -> real signed adapter
    from .binance import BinanceAdapter

    adapter = BinanceAdapter(settings)
    await adapter.sync_time()
    return adapter


__all__ = ["ExchangeAdapter", "PaperAdapter", "build_adapter"]
