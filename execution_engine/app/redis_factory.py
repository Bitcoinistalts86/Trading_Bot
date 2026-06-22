# execution_engine/app/redis_factory.py
"""
One place to build an async Redis client.

Managed Redis (Railway, Upstash, ElastiCache with auth) is reached via a single
connection URL that carries credentials, e.g.
`redis://default:password@host:6379` or `rediss://...` for TLS. Local/dev and
GKE typically use plain host/port. This helper prefers `REDIS_URL` when set and
falls back to host/port, returning a *connected* client or None so callers can
degrade to in-memory.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("execution_engine.redis_factory")


async def connect_redis(redis_host: str = "", redis_port: int = 6379):
    """Return a connected async Redis client, or None if unavailable/unconfigured."""
    url = os.environ.get("REDIS_URL")
    if not (url or redis_host):
        return None
    try:
        import redis.asyncio as redis  # lazy by design
        client = (
            redis.from_url(url, decode_responses=True)
            if url
            else redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        )
        await client.ping()
        logger.info("Connected to Redis via %s", "REDIS_URL" if url else f"{redis_host}:{redis_port}")
        return client
    except Exception as exc:  # noqa: BLE001 -- never crash startup on Redis
        logger.error("Redis unavailable (%s). Falling back to in-memory.", exc)
        return None
