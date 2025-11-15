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

    async def record_latency(self, exchange: str, latency_ms: float):
        """Records a latency measurement for a given exchange."""
        key = f"latency_metrics:{exchange}"
        await self.client.lpush(key, latency_ms)
        # Trim the list to keep only the last 100 measurements
        await self.client.ltrim(key, 0, 99)

    def _user_positions_key(self, user_id: str) -> str:
        return f"positions:{user_id}"

    async def get_user_positions(self, user_id: str) -> dict:
        """Gets the current positions for a specific user."""
        return await self.client.hgetall(self._user_positions_key(user_id))

    async def update_user_position(self, user_id: str, instrument: str, quantity: float):
        """Updates the position for a specific user and instrument."""
        await self.client.hset(self._user_positions_key(user_id), instrument, quantity)

    async def close(self):
        """Closes the Redis connection."""
        await self.client.close()

# --- Factory function for easy initialization ---
def get_redis_client() -> RedisStateClient:
    """Initializes and returns the RedisStateClient from environment variables."""
    redis_host = os.environ.get("REDIS_HOST")
    redis_port = int(os.environ.get("REDIS_PORT", 6379))
    return RedisStateClient(host=redis_host, port=redis_port)
