# chaos_tests/test_redis_outage.py
import asyncio
import httpx
import redis
import os

API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL")
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

async def test_redis_outage():
    """
    Simulates a Redis outage by setting the kill-switch and then
    verifies that the api_gateway rejects orders.
    """
    print("--- Running Chaos Test: Redis Outage ---")

    # 1. Simulate Redis being "down" by activating the HARD kill-switch
    print("Step 1: Activating HARD kill-switch...")
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    redis_client.set("killswitch:level", "HARD")
    print("Kill-switch set to HARD.")

    # 2. Try to place an order via the api_gateway
    print("Step 2: Attempting to place an order (should fail)...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{API_GATEWAY_URL}/api/order", json={"instrument": "BTC/USD", "side": "buy", "quantity": 1})
            if response.status_code == 503:
                print("SUCCESS: API Gateway correctly rejected the order.")
            else:
                print(f"FAILURE: API Gateway returned status code {response.status_code} instead of 503.")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 503:
                 print("SUCCESS: API Gateway correctly rejected the order.")
            else:
                 print(f"FAILURE: API Gateway returned status code {e.response.status_code} instead of 503.")


    # 3. Clean up by turning the kill-switch off
    print("Step 3: Cleaning up - Deactivating kill-switch...")
    redis_client.set("killswitch:level", "OFF")
    print("Kill-switch set to OFF.")
    print("--- Chaos Test: Redis Outage Complete ---")

if __name__ == "__main__":
    asyncio.run(test_redis_outage())
