# api_gateway/app/main.py
import asyncio
import json
import logging
import os
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import List

from .websocket_router import ConnectionManager, broadcast_to_clients
from .pubsub_consumer import start_pubsub_listener
from .auth import get_current_user
from ..libraries.state.redis_state import get_redis_client, RedisStateClient

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
EXECUTION_ENGINE_URL = os.environ.get("EXECUTION_ENGINE_URL")

# --- FastAPI App ---
app = FastAPI(title="API Gateway")
manager = ConnectionManager()
redis_client: RedisStateClient = None

@app.on_event("startup")
async def startup_event():
    """On startup, initialize clients and start background tasks."""
    global redis_client
    redis_client = get_redis_client()
    # Start the Pub/Sub listener as a background task
    asyncio.create_task(start_pubsub_listener(manager))

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown, close client connections."""
    if redis_client:
        await redis_client.close()

# --- WebSockets ---
@app.websocket("/ws/features")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming real-time features."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logging.info("Client disconnected from WebSocket.")

# --- REST Endpoints ---
@app.post("/api/order")
async def place_order(order: dict, current_user: dict = Depends(get_current_user)):
    """
    Places an order by forwarding the request to the execution engine.
    (This is a simplified passthrough for now).
    """
    if not EXECUTION_ENGINE_URL:
        raise HTTPException(status_code=500, detail="Execution engine URL not configured.")

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{EXECUTION_ENGINE_URL}/order", json=order)
        response.raise_for_status()
        return response.json()

@app.get("/api/killswitch")
async def get_killswitch_status(current_user: dict = Depends(get_current_user)):
    """Gets the current state of the global kill-switch from Redis."""
    is_active = await redis_client.is_killswitch_active()
    return {"killswitch_active": is_active}

@app.post("/api/killswitch")
async def set_killswitch_status(active: bool, current_user: dict = Depends(get_current_user)):
    """Sets the state of the global kill-switch in Redis."""
    await redis_client.set_killswitch(active)
    return {"status": "ok", "killswitch_active": active}

@app.get("/health")
def health_check():
    return {"status": "ok"}
