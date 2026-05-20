# execution_engine/main.py
import os
import uuid
import json
import logging
import asyncio
import threading
from datetime import datetime, timezone
from typing import Optional, List, Dict
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from google.cloud import pubsub_v1

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("execution_engine")

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "test-project")
PUBSUB_EMULATOR_HOST = os.environ.get("PUBSUB_EMULATOR_HOST")

if PUBSUB_EMULATOR_HOST:
    os.environ["PUBSUB_EMULATOR_HOST"] = PUBSUB_EMULATOR_HOST

# --- Models ---
class Signal(BaseModel):
    strategy_id: str
    instrument: str
    side: str
    price_target: float
    quantity: float
    order_type: str # "MARKET", "LIMIT", "TWAP", "VWAP"
    duration_seconds: Optional[int] = 60 # For TWAP/VWAP

class Order(BaseModel):
    instrument: str
    side: str
    quantity: float
    price: Optional[float] = None
    order_type: str # "MARKET", "LIMIT", "TWAP", "VWAP"
    duration_seconds: Optional[int] = 60

# --- In-memory State (Simulation) ---
STATE = {
    "kill_switch_active": False,
    "portfolio": {"USD": 100000.0, "ETH": 0.0},
    "positions": [],
    "last_price": 2500.0
}

# --- Risk Manager ---
def check_risk(order: Order) -> bool:
    if STATE["kill_switch_active"]:
        logger.warning("Risk Check Failed: Kill-switch is active")
        return False

    price = order.price or STATE["last_price"]
    total_value = order.quantity * price

    if order.side == "BUY" and STATE["portfolio"]["USD"] < total_value:
        logger.warning(f"Risk Check Failed: Insufficient USD balance ({STATE['portfolio']['USD']} < {total_value})")
        return False

    if order.side == "SELL" and STATE["portfolio"]["ETH"] < order.quantity:
        logger.warning(f"Risk Check Failed: Insufficient ETH balance ({STATE['portfolio']['ETH']} < {order.quantity})")
        return False

    return True

# --- Execution Manager ---
async def publish_execution(order_id: str, instrument: str, side: str, quantity: float, price: float):
    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, "market.executions")
        data = json.dumps({
            "order_id": order_id,
            "instrument": instrument,
            "side": side,
            "quantity": quantity,
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }).encode("utf-8")
        publisher.publish(topic_path, data)
    except Exception as e:
        logger.warning(f"Could not publish execution: {e}")

async def execute_immediate(order: Order):
    logger.info(f"Executing Immediate {order.order_type}: {order}")
    await asyncio.sleep(0.1) # Network latency simulation

    price = order.price or STATE["last_price"]
    total_value = order.quantity * price

    if order.side == "BUY":
        STATE["portfolio"]["USD"] -= total_value
        STATE["portfolio"]["ETH"] += order.quantity
    else:
        STATE["portfolio"]["USD"] += total_value
        STATE["portfolio"]["ETH"] -= order.quantity

    STATE["last_price"] = price
    await publish_execution(str(uuid.uuid4()), order.instrument, order.side, order.quantity, price)

async def execute_twap(order: Order):
    """Time-Weighted Average Price execution."""
    duration = order.duration_seconds or 60
    chunks = 10
    interval = duration / chunks
    qty_per_chunk = order.quantity / chunks

    logger.info(f"Starting TWAP for {order.quantity} {order.instrument} over {duration}s in {chunks} chunks")

    for i in range(chunks):
        if STATE["kill_switch_active"]:
            logger.warning("TWAP Aborted: Kill-switch activated")
            break

        # Simulated slight price variance for each chunk
        current_price = STATE["last_price"] * (1 + (0.0001 * (i % 3 - 1)))

        chunk_order = Order(
            instrument=order.instrument,
            side=order.side,
            quantity=qty_per_chunk,
            price=current_price,
            order_type="MARKET"
        )

        # Internal immediate execution for chunk
        total_value = qty_per_chunk * current_price
        if order.side == "BUY":
            STATE["portfolio"]["USD"] -= total_value
            STATE["portfolio"]["ETH"] += qty_per_chunk
        else:
            STATE["portfolio"]["USD"] += total_value
            STATE["portfolio"]["ETH"] -= qty_per_chunk

        await publish_execution(f"twap-{uuid.uuid4()}", order.instrument, order.side, qty_per_chunk, current_price)
        logger.info(f"TWAP Chunk {i+1}/{chunks} executed at {current_price}")

        await asyncio.sleep(interval)

async def execute_vwap(order: Order):
    """Volume-Weighted Average Price execution (Simulated volume profile)."""
    duration = order.duration_seconds or 60
    chunks = 10
    interval = duration / chunks

    # Simulated volume profile: more volume at start and end of interval (U-shaped)
    profile = [0.15, 0.1, 0.08, 0.07, 0.05, 0.05, 0.07, 0.1, 0.15, 0.18]

    logger.info(f"Starting VWAP for {order.quantity} {order.instrument} over {duration}s")

    for i in range(chunks):
        if STATE["kill_switch_active"]:
            logger.warning("VWAP Aborted: Kill-switch activated")
            break

        qty_per_chunk = order.quantity * profile[i]
        current_price = STATE["last_price"]

        total_value = qty_per_chunk * current_price
        if order.side == "BUY":
            STATE["portfolio"]["USD"] -= total_value
            STATE["portfolio"]["ETH"] += qty_per_chunk
        else:
            STATE["portfolio"]["USD"] += total_value
            STATE["portfolio"]["ETH"] -= qty_per_chunk

        await publish_execution(f"vwap-{uuid.uuid4()}", order.instrument, order.side, qty_per_chunk, current_price)
        logger.info(f"VWAP Chunk {i+1}/{chunks} executed {qty_per_chunk} at {current_price}")

        await asyncio.sleep(interval)

async def route_order(order: Order):
    if order.order_type in ["MARKET", "LIMIT"]:
        await execute_immediate(order)
    elif order.order_type == "TWAP":
        await execute_twap(order)
    elif order.order_type == "VWAP":
        await execute_vwap(order)
    else:
        logger.error(f"Unsupported order type: {order.order_type}")

# --- Pub/Sub Subscriber for Signals ---
def start_signal_subscriber(loop):
    try:
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = f"projects/{PROJECT_ID}/subscriptions/market.signals.sub"

        def callback(message):
            logger.info(f"Received signal from Pub/Sub: {message.data}")
            try:
                data = json.loads(message.data)
                signal = Signal(**data)
                order = Order(
                    instrument=signal.instrument,
                    side=signal.side,
                    quantity=signal.quantity,
                    price=signal.price_target,
                    order_type=signal.order_type,
                    duration_seconds=signal.duration_seconds
                )

                if check_risk(order):
                    # Schedule on the main event loop
                    asyncio.run_coroutine_threadsafe(route_order(order), loop)

                message.ack()
            except Exception as e:
                logger.error(f"Error processing signal: {e}")
                message.nack()

        logger.info(f"Listening for signals on {subscription_path}...")
        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    except Exception as e:
        logger.warning(f"Could not initialize Pub/Sub subscriber: {e}")

# --- FastAPI App ---
app = FastAPI(title="Execution Engine")

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    # Start Pub/Sub subscriber in a separate thread
    threading.Thread(target=start_signal_subscriber, args=(loop,), daemon=True).start()

@app.post("/order")
async def place_order(order: Order, background_tasks: BackgroundTasks):
    if not check_risk(order):
        raise HTTPException(status_code=400, detail="Risk check failed")

    background_tasks.add_task(route_order, order)
    return {"status": "order_accepted", "order": order}

@app.post("/kill-switch")
async def kill_switch(action: str):
    if action == "ACTIVATE":
        STATE["kill_switch_active"] = True
        logger.warning("KILL-SWITCH ACTIVATED")
    else:
        STATE["kill_switch_active"] = False
        logger.info("KILL-SWITCH DEACTIVATED")
    return {"status": "ok", "kill_switch_active": STATE["kill_switch_active"]}

@app.get("/positions")
async def get_positions():
    return {
        "USD": STATE["portfolio"]["USD"],
        "ETH": STATE["portfolio"]["ETH"],
        "USD_PRICE": STATE["last_price"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
