# chaos_tests/test_gateway_connection_drop.py
import asyncio
import httpx
import redis
import os
import websockets

API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL", "ws://localhost:8000")
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))

async def test_gateway_connection_drop():
    """
    Simulates a gateway connection drop by activating the HARD kill-switch
    and verifying that the WebSocket connection is terminated.
    """
    print("--- Running Chaos Test: Gateway Connection Drop ---")

    # 1. Establish a WebSocket connection
    ws_url = f"{API_GATEWAY_URL.replace('http', 'ws')}/ws/features"
    async with websockets.connect(ws_url) as websocket:
        print("Step 1: WebSocket connection established.")

        # 2. Activate the HARD kill-switch
        print("Step 2: Activating HARD kill-switch...")
        redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        redis_client.set("killswitch:level", "HARD")
        print("Kill-switch set to HARD.")

        # 3. Verify that the connection is closed by the server
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            print(f"FAILURE: Received unexpected message: {message}")
        except (websockets.exceptions.ConnectionClosed, asyncio.TimeoutError):
            print("SUCCESS: WebSocket connection was correctly terminated by the server.")

    # 4. Clean up
    print("Step 4: Cleaning up - Deactivating kill-switch...")
    redis_client.set("killswitch:level", "OFF")
    print("Kill-switch set to OFF.")
    print("--- Chaos Test: Gateway Connection Drop Complete ---")

if __name__ == "__main__":
    asyncio.run(test_gateway_connection_drop())
