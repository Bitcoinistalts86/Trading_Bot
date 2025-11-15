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
        self.global_key = "killswitch:global"

    def _user_key(self, user_id: str) -> str:
        return f"killswitch:user:{user_id}"

    async def get_user_level(self, user_id: str) -> KillSwitchLevel:
        """Gets the kill-switch level for a specific user."""
        level = await self.client.get(self._user_key(user_id))
        if level is None:
            return KillSwitchLevel.OFF
        try:
            return KillSwitchLevel(level)
        except ValueError:
            logging.warning(f"Invalid kill-switch level '{level}' in Redis for user {user_id}. Defaulting to OFF.")
            return KillSwitchLevel.OFF

    async def set_user_level(self, user_id: str, level: KillSwitchLevel):
        """Sets the kill-switch level for a specific user."""
        await self.client.set(self._user_key(user_id), level.value)
        logging.info(f"User kill-switch for {user_id} has been set to {level.value}")

    async def get_global_level(self) -> KillSwitchLevel:
        """Gets the global kill-switch level."""
        level = await self.client.get(self.global_key)
        if level is None:
            return KillSwitchLevel.OFF
        try:
            return KillSwitchLevel(level)
        except ValueError:
            logging.warning(f"Invalid global kill-switch level '{level}' in Redis. Defaulting to OFF.")
            return KillSwitchLevel.OFF

    async def set_global_level(self, level: KillSwitchLevel):
        """Sets the global kill-switch level."""
        await self.client.set(self.global_key, level.value)
        logging.warning(f"Global kill-switch has been set to {level.value}")

    async def is_soft_kill_active(self, user_id: str) -> bool:
        """Checks if a soft or hard kill is active for a user or globally."""
        user_level = await self.get_user_level(user_id)
        global_level = await self.get_global_level()
        return user_level in [KillSwitchLevel.SOFT, KillSwitchLevel.HARD] or \
               global_level in [KillSwitchLevel.SOFT, KillSwitchLevel.HARD]

    async def is_hard_kill_active(self, user_id: str) -> bool:
        """Checks if a hard kill is active for a user or globally."""
        user_level = await self.get_user_level(user_id)
        global_level = await self.get_global_level()
        return user_level == KillSwitchLevel.HARD or global_level == KillSwitchLevel.HARD

def get_kill_switch_client(redis_client: redis.Redis) -> KillSwitchClient:
    """Initializes and returns the KillSwitchClient."""
    return KillSwitchClient(client=redis_client)
