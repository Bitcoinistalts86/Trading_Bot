# execution_engine/app/kill_switch.py
"""
Reconciles the two legacy kill-switch implementations:

  * `execution_engine/main.py` used a plain in-process boolean
    (`STATE["kill_switch_active"]`) that reset on restart and was NOT shared
    across replicas -- useless as a real safety guard.
  * `execution_engine/app/main.py` used the Redis-backed multi-level
    `libraries.state.kill_switch.KillSwitchClient`, but imported it via a broken
    relative path and had no redis dependency, so it never ran.

The Redis-backed multi-level switch is the correct design and wins. This module
prefers it, and provides an in-memory shim with the *same async interface* so the
engine still runs in tests / local dev without Redis -- but the shim is clearly a
single-process fallback, not a substitute for shared state in production.
"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("execution_engine.kill_switch")


class KillSwitchLevel(str, Enum):
    OFF = "OFF"
    SOFT = "SOFT"   # reject new orders, let in-flight finish
    HARD = "HARD"   # halt everything immediately


class _InMemoryKillSwitch:
    """Single-process fallback. Same async surface as the Redis client."""

    def __init__(self) -> None:
        self._global = KillSwitchLevel.OFF
        self._users: dict[str, KillSwitchLevel] = {}
        logger.warning("Using IN-MEMORY kill-switch fallback (not shared across replicas).")

    async def get_global_level(self) -> KillSwitchLevel:
        return self._global

    async def set_global_level(self, level: KillSwitchLevel) -> None:
        self._global = level
        logger.warning("Global kill-switch set to %s", level.value)

    async def get_user_level(self, user_id: str) -> KillSwitchLevel:
        return self._users.get(user_id, KillSwitchLevel.OFF)

    async def set_user_level(self, user_id: str, level: KillSwitchLevel) -> None:
        self._users[user_id] = level
        logger.info("User %s kill-switch set to %s", user_id, level.value)

    async def is_soft_kill_active(self, user_id: str) -> bool:
        u = await self.get_user_level(user_id)
        return u in (KillSwitchLevel.SOFT, KillSwitchLevel.HARD) or \
            self._global in (KillSwitchLevel.SOFT, KillSwitchLevel.HARD)

    async def is_hard_kill_active(self, user_id: str) -> bool:
        u = await self.get_user_level(user_id)
        return u == KillSwitchLevel.HARD or self._global == KillSwitchLevel.HARD


async def build_kill_switch(redis_host: str, redis_port: int):
    """
    Return a kill-switch client. Prefers the shared Redis-backed implementation
    from `libraries.state`; falls back to in-memory if Redis or the library is
    unavailable.
    """
    from .redis_factory import connect_redis
    client = await connect_redis(redis_host, redis_port)
    if client is None:
        return _InMemoryKillSwitch()
    try:
        from libraries.state.kill_switch import get_kill_switch_client  # type: ignore
        return get_kill_switch_client(client)
    except Exception as exc:  # noqa: BLE001 -- degrade gracefully, never crash startup
        logger.error("Kill-switch library unavailable (%s). Falling back to in-memory.", exc)
        return _InMemoryKillSwitch()
