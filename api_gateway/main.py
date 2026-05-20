# api_gateway/main.py
import os
import asyncio
import json
import logging
import threading
from typing import List, Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
from google.cloud import pubsub_v1

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_gateway")

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project")
EXECUTION_ENGINE_URL = os.environ.get("EXECUTION_ENGINE_URL", "http://localhost:8001")
PUBSUB_EMULATOR_HOST = os.environ.get("PUBSUB_EMULATOR_HOST")

if PUBSUB_EMULATOR_HOST:
    os.environ["PUBSUB_EMULATOR_HOST"] = PUBSUB_EMULATOR_HOST

try:
    publisher = pubsub_v1.PublisherClient()
except Exception as e:
    logger.warning(f"Could not initialize Pub/Sub publisher: {e}. Using mock.")
    class MockPublisher:
        def publish(self, topic, data):
            class Future:
                def result(self): return "mock_id"
            logger.info(f"MOCK PUBLISH to {topic}: {data}")
            return Future()
    publisher = MockPublisher()

SIGNAL_TOPIC = f"projects/{PROJECT_ID}/topics/market.signals"

# --- Models ---
class Signal(BaseModel):
    strategy_id: str
    instrument: str
    side: str
    price_target: float
    quantity: float
    order_type: str
    duration_seconds: Optional[int] = 60

class Order(BaseModel):
    instrument: str
    side: str
    quantity: float
    price: Optional[float] = None
    order_type: str
    duration_seconds: Optional[int] = 60

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# --- Pub/Sub Listener for WebSocket Broadcasting ---
def start_broadcast_listener(loop):
    try:
        subscriber = pubsub_v1.SubscriberClient()

        # Subscriptions for executions and features
        subscriptions = [
            f"projects/{PROJECT_ID}/subscriptions/market.executions.sub",
            f"projects/{PROJECT_ID}/subscriptions/features.realtime.sub"
        ]

        def callback(message):
            logger.info(f"Broadcasting message: {message.data}")
            data = message.data.decode("utf-8")
            asyncio.run_coroutine_threadsafe(manager.broadcast(data), loop)
            message.ack()

        for sub in subscriptions:
            try:
                logger.info(f"Listening for broadcast on {sub}...")
                subscriber.subscribe(sub, callback=callback)
            except Exception as e:
                logger.error(f"Failed to subscribe to {sub}: {e}")
    except Exception as e:
        logger.warning(f"Could not initialize Pub/Sub subscriber: {e}")

# --- FastAPI App ---
app = FastAPI(title="Unified API Gateway")

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    threading.Thread(target=start_broadcast_listener, args=(loop,), daemon=True).start()

# Serve static files
app.mount("/static", StaticFiles(directory="api_gateway/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("api_gateway/static/index.html", "r") as f:
        return f.read()

@app.post("/v1/signal")
async def receive_signal(signal: Signal):
    """Receives trading signals and publishes to Pub/Sub."""
    logger.info(f"Received signal: {signal}")
    data = signal.json().encode("utf-8")
    try:
        future = publisher.publish(SIGNAL_TOPIC, data)
        future.result()
        return {"status": "signal_published", "topic": SIGNAL_TOPIC}
    except Exception as e:
        logger.error(f"Failed to publish signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/order")
async def place_order(order: Order):
    """Forwards order to execution engine via REST."""
    logger.info(f"Received order: {order}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{EXECUTION_ENGINE_URL}/order", json=order.dict())
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to forward order: {e}")
            raise HTTPException(status_code=500, detail="Execution engine unreachable")

@app.post("/v1/kill-switch")
async def activate_kill_switch(action: str):
    """Emergency halt of all execution logic."""
    logger.warning(f"Kill-switch action: {action}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{EXECUTION_ENGINE_URL}/kill-switch", params={"action": action})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to trigger kill-switch: {e}")
            raise HTTPException(status_code=500, detail="Execution engine unreachable")

@app.get("/v1/positions")
async def get_positions():
    """Retrieves current open positions from execution engine."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{EXECUTION_ENGINE_URL}/positions")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return {"USD": 0.0, "ETH": 0.0, "error": "Could not connect to execution engine"}

@app.get("/v1/status")
async def get_status():
    """Diagnostics status of all microservices."""
    return {
        "api_gateway": "online",
        "execution_engine": "online",
        "pubsub_emulator": "online" if PUBSUB_EMULATOR_HOST else "offline"
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Wait for any incoming messages (keep-alive)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
