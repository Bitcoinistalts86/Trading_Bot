# execution_engine/app/risk_state.py
"""
Durable, shareable risk state.

The pieces of risk state that the PositionStore does NOT cover -- the per-minute
order-rate window and the daily realized-loss counter -- lived in process memory.
That meant a crash reset the daily-loss stand-down (the engine would forget it
had already lost money and resume), and the rate limit was per-replica rather
than global. Both are safety-relevant, so they move to Redis.

Mirrors the kill-switch pattern: prefer Redis, fall back to an in-memory
implementation (single-process) so tests and local dev run without Redis. The
async surface is identical across both.

Keys (Redis):
  risk:orders               ZSET of order timestamps (score = epoch seconds), TTL 120s
  risk:pnl:{YYYYMMDD}       FLOAT daily realized PnL, TTL 48h (auto day-rollover)
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import deque

logger = logging.getLogger("execution_engine.risk_state")

_ORDERS_KEY = "risk:orders"
_PNL_PREFIX = "risk:pnl:"
_ORDERS_TTL = 120
_PNL_TTL = 48 * 3600


class InMemoryRiskState:
    """Single-process fallback. Same async surface as the Redis implementation."""

    def __init__(self) -> None:
        self._orders: deque[float] = deque(maxlen=100_000)
        self._pnl: dict[str, float] = {}
        logger.warning("Using IN-MEMORY risk state (not durable across restarts/replicas).")

    async def trim_and_count_orders(self, now: float, window: float) -> int:
        cutoff = now - window
        while self._orders and self._orders[0] < cutoff:
            self._orders.popleft()
        return len(self._orders)

    async def add_order(self, now: float) -> None:
        self._orders.append(now)

    async def get_realized_pnl(self, day_key: str) -> float:
        return self._pnl.get(day_key, 0.0)

    async def add_realized_pnl(self, day_key: str, delta: float) -> float:
        self._pnl[day_key] = self._pnl.get(day_key, 0.0) + delta
        return self._pnl[day_key]


class RedisRiskState:
    """Durable, cross-replica risk state backed by Redis."""

    def __init__(self, client) -> None:
        self._r = client

    async def trim_and_count_orders(self, now: float, window: float) -> int:
        await self._r.zremrangebyscore(_ORDERS_KEY, 0, now - window)
        return int(await self._r.zcard(_ORDERS_KEY))

    async def add_order(self, now: float) -> None:
        # Unique member so two orders in the same instant don't collide.
        await self._r.zadd(_ORDERS_KEY, {f"{now:.6f}:{uuid.uuid4().hex}": now})
        await self._r.expire(_ORDERS_KEY, _ORDERS_TTL)

    async def get_realized_pnl(self, day_key: str) -> float:
        val = await self._r.get(_PNL_PREFIX + day_key)
        return float(val) if val is not None else 0.0

    async def add_realized_pnl(self, day_key: str, delta: float) -> float:
        key = _PNL_PREFIX + day_key
        total = float(await self._r.incrbyfloat(key, delta))
        await self._r.expire(key, _PNL_TTL)
        return total


async def build_risk_state(redis_host: str, redis_port: int):
    """Prefer Redis (REDIS_URL or host/port); fall back to in-memory."""
    from .redis_factory import connect_redis
    client = await connect_redis(redis_host, redis_port)
    return RedisRiskState(client) if client is not None else InMemoryRiskState()
