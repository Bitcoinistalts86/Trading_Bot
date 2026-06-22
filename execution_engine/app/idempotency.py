# execution_engine/app/idempotency.py
"""
Idempotency & duplicate-order protection.

Pub/Sub delivers signals at-least-once, and a crash can land between sending an
order and recording it. Without protection, a redelivered or duplicated signal
places a *second* real order. Two layers fix this:

  1. Engine-level dedup -- an IdempotencyStore claims each logical order key
     atomically (Redis SET NX). A duplicate key is suppressed before it ever
     reaches risk/execution.
  2. Exchange-level dedup -- the order's `newClientOrderId` is *deterministic*
     from the same key, so even if layer 1 is bypassed (cross-replica race
     resolved by Redis, or a redelivery after restart), Binance rejects the
     second order as a duplicate clientOrderId.

Both the Redis store and the in-memory fallback share one async surface, mirroring
the kill-switch / risk-state pattern.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

logger = logging.getLogger("execution_engine.idempotency")

_PREFIX = "idem:"
STATUS_PENDING = "PENDING"
STATUS_DONE = "DONE"


def deterministic_client_order_id(key: str) -> str:
    """Stable, Binance-valid (<=36 char) clientOrderId derived from an idem key."""
    digest = hashlib.sha1(key.encode()).hexdigest()[:24]
    return f"x-{digest}"  # 26 chars; matches ^[A-Za-z0-9-_.:/]{1,36}$


class InMemoryIdempotencyStore:
    """Single-process fallback. Same async surface as the Redis implementation."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, dict]] = {}  # key -> (expiry_ts, record)
        logger.warning("Using IN-MEMORY idempotency store (not shared across replicas).")

    def _evict(self, now: float) -> None:
        for k in [k for k, (exp, _) in self._data.items() if exp < now]:
            self._data.pop(k, None)

    async def begin(self, key: str, ttl: int) -> tuple[bool, dict | None]:
        now = time.time()
        self._evict(now)
        if key in self._data:
            return False, self._data[key][1]
        record = {"status": STATUS_PENDING, "ts": now}
        self._data[key] = (now + ttl, record)
        return True, None

    async def complete(self, key: str, result: dict, ttl: int) -> None:
        self._data[key] = (time.time() + ttl, {"status": STATUS_DONE, **result})


class RedisIdempotencyStore:
    """Durable, cross-replica dedup backed by Redis."""

    def __init__(self, client) -> None:
        self._r = client

    async def begin(self, key: str, ttl: int) -> tuple[bool, dict | None]:
        rkey = _PREFIX + key
        record = json.dumps({"status": STATUS_PENDING, "ts": time.time()})
        # Atomic claim: only the first caller sets the key.
        won = await self._r.set(rkey, record, nx=True, ex=ttl)
        if won:
            return True, None
        existing = await self._r.get(rkey)
        return False, (json.loads(existing) if existing else {"status": STATUS_PENDING})

    async def complete(self, key: str, result: dict, ttl: int) -> None:
        rkey = _PREFIX + key
        await self._r.set(rkey, json.dumps({"status": STATUS_DONE, **result}), ex=ttl)


async def build_idempotency_store(redis_host: str, redis_port: int):
    """Prefer Redis (REDIS_URL or host/port); fall back to in-memory."""
    from .redis_factory import connect_redis
    client = await connect_redis(redis_host, redis_port)
    return RedisIdempotencyStore(client) if client is not None else InMemoryIdempotencyStore()


async def run_idempotent(store, key: str, ttl: int, fn):
    """
    Run `fn` at most once per key. Returns (executed: bool, result).
      * executed=True  -> fn ran; result is fn's return value.
      * executed=False -> duplicate suppressed; result is the prior record.
    On exception the key is left PENDING (claimed) so we never re-send an order
    whose fate is unknown; exchange-level deterministic clientOrderId guards the
    rest. Callers that know fn did NOT touch the venue may choose to re-raise.
    """
    is_new, prior = await store.begin(key, ttl)
    if not is_new:
        logger.warning("Duplicate suppressed for idempotency key %s (prior=%s)",
                       key, (prior or {}).get("status"))
        return False, prior
    result = await fn()
    summary = result if isinstance(result, dict) else {"ok": True}
    await store.complete(key, summary, ttl)
    return True, result
