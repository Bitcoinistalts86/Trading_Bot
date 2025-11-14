# libraries/state/kill_switch.py
import redis.asyncio as redis
import os
import logging
from enum import Enum

class KillSwitchLevel(Enum):
    """Enumeration for kill-switch levels."""
    OFF = "OFF"
    SOFT = "SOFT"
    HARD = "HARD"

class KillSwitchClient:
    """A client for managing the multi-level kill-switch in Redis."""

    def __init__(self, client: redis.Redis):
        if not client:
            raise ValueError("Redis client must be provided.")
        self.client = client
        self.key = "killswitch:level"

    async def get_level(self) -> KillSwitchLevel:
        """Gets the current kill-switch level."""
        level = await self.client.get(self.key)
        if level is None:
            return KillSwitchLevel.OFF
        try:
            return KillSwitchLevel(level)
        except ValueError:
            logging.warning(f"Invalid kill-switch level '{level}' in Redis. Defaulting to OFF.")
            return KillSwitchLevel.OFF

    async def set_level(self, level: KillSwitchLevel):
        """Sets the kill-switch level."""
        await self.client.set(self.key, level.value)
        logging.warning(f"Global kill-switch has been set to {level.value}")

    async def is_soft_kill_active(self) -> bool:
        """Checks if a soft or hard kill is active."""
        level = await self.get_level()
        return level in [KillSwitchLevel.SOFT, KillSwitchLevel.HARD]

    async def is_hard_kill_active(self) -> bool:
        """Checks if a hard kill is active."""
        return await self.get_level() == KillSwitchLevel.HARD

def get_kill_switch_client(redis_client: redis.Redis) -> KillSwitchClient:
    """Initializes and returns the KillSwitchClient."""
    return KillSwitchClient(client=redis_client)
