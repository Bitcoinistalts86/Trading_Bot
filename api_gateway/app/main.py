# api_gateway/app/main.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import asyncio
import json
import logging
import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import List
from httpx_retry import RetryTransport
import pybreaker

from api_gateway.app.websocket_router import ConnectionManager, broadcast_to_clients
from api_gateway.app.pubsub_consumer import start_pubsub_listener
from libraries.auth import get_current_user, TokenData
from libraries.state.redis_state import get_redis_client, RedisStateClient
from libraries.state.kill_switch import get_kill_switch_client, KillSwitchClient, KillSwitchLevel

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
EXECUTION_ENGINE_URL = os.environ.get("EXECUTION_ENGINE_URL")

# --- FastAPI App ---
app = FastAPI(title="API Gateway")
manager = ConnectionManager()
redis_client: RedisStateClient = None
kill_switch_client: KillSwitchClient = None
execution_engine_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
LOG = logging.getLogger("api_gateway")
logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def startup_event():
    """On startup, initialize clients and start background tasks."""
    global redis_client, kill_switch_client
    redis_client = get_redis_client()
    kill_switch_client = get_kill_switch_client(redis_client.client)
    # Start the Pub/Sub listener as a background task
    asyncio.create_task(start_pubsub_listener(manager))

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown, close client connections."""
    if redis_client:
        await redis_client.close()

# --- WebSockets ---
@app.websocket("/ws/features")
async def websocket_endpoint(websocket: WebSocket, token: str = Depends(get_current_user)):
    """WebSocket endpoint for streaming real-time features."""
    await manager.connect(websocket)
    try:
        while True:
            if await kill_switch_client.is_hard_kill_active(token.user_id):
                logging.warning("HARD kill-switch active. Closing WebSocket connection.")
                await websocket.close(code=status.WS_1012_SERVICE_RESTART)
                manager.disconnect(websocket)
                break
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logging.info("Client disconnected from WebSocket.")

# --- REST Endpoints ---
@app.post("/api/order")
async def place_order(order: dict, current_user: TokenData = Depends(get_current_user)):
    """
    Places an order by forwarding the request to the execution engine.
    (This is a simplified passthrough for now).
    """
    if await kill_switch_client.is_soft_kill_active(current_user.user_id):
        raise HTTPException(status_code=503, detail="Service is temporarily unavailable due to kill-switch activation.")

    if not EXECUTION_ENGINE_URL:
        raise HTTPException(status_code=500, detail="Execution engine URL not configured.")

    @execution_engine_breaker
    async def call_execution_engine():
        transport = RetryTransport(
            wrapped_transport=httpx.AsyncHTTPTransport(),
            max_attempts=3,
            backoff_factor=2,
            status_forcelist=[500, 502, 503, 504],
        )
        # Add user_id to the order payload
        order_payload = order.copy()
        order_payload["user_id"] = current_user.user_id

        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.post(f"{EXECUTION_ENGINE_URL}/order", json=order_payload)
            response.raise_for_status()
            return response.json()

    try:
        return await call_execution_engine()
    except pybreaker.CircuitBreakerError:
        raise HTTPException(status_code=503, detail="Execution engine is currently unavailable.")

@app.get("/api/killswitch")
async def get_killswitch_status(current_user: TokenData = Depends(get_current_user)):
    """Gets the current state of the user's kill-switch from Redis."""
    level = await kill_switch_client.get_user_level(current_user.user_id)
    return {"kill_switch_level": level.value}

@app.post("/api/killswitch")
async def set_killswitch_status(level: KillSwitchLevel, current_user: TokenData = Depends(get_current_user)):
    """Sets the state of the user's kill-switch in Redis."""
    await kill_switch_client.set_user_level(current_user.user_id, level)
    return {"status": "ok", "kill_switch_level": level.value}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# ASGI-compatible. Uvicorn must be run from a separate file.
pass
