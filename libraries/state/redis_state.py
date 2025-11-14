# libraries/state/redis_state.py
import redis.asyncio as redis
import os
import logging

class RedisStateClient:
    """A client for managing shared state in Redis."""

    def __init__(self, host: str, port: int):
        if not host:
            raise ValueError("Redis host must be provided.")
        self.client = redis.Redis(host=host, port=port, decode_responses=True)
        logging.info(f"Redis client initialized for host {host}:{port}")

    async def is_killswitch_active(self) -> bool:
        """Checks if the global kill-switch is active."""
        return await self.client.get("killswitch.enabled") == "true"

    async def set_killswitch(self, active: bool):
        """Sets the state of the global kill-switch."""
        await self.client.set("killswitch.enabled", "true" if active else "false")
        logging.warning(f"Global kill-switch has been set to {active}")

    async def record_latency(self, exchange: str, latency_ms: float):
        """Records a latency measurement for a given exchange."""
        key = f"latency_metrics:{exchange}"
        await self.client.lpush(key, latency_ms)
        # Trim the list to keep only the last 100 measurements
        await self.client.ltrim(key, 0, 99)

    # Add other state management methods as needed, e.g.:
    # async def throttle_order(self, instrument: str) -> bool: ...
    # async def update_last_signal_timestamp(self, ts: float): ...

    async def close(self):
        """Closes the Redis connection."""
        await self.client.close()

# --- Factory function for easy initialization ---
def get_redis_client() -> RedisStateClient:
    """Initializes and returns the RedisStateClient from environment variables."""
    redis_host = os.environ.get("REDIS_HOST")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    return RedisStateClient(host=redis_host, port=redis_port)
