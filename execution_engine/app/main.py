# execution_engine/app/main.py
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
from google.cloud import pubsub_v1, bigquery

# Import the shared Redis client
from ..libraries.state.redis_state import get_redis_client, RedisStateClient

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
# ... (rest of configuration is the same)

# --- Clients ---
app = FastAPI(title="Execution Engine")
redis_client: RedisStateClient = None # Will be initialized on startup
bq_client = bigquery.Client()
http_client = httpx.AsyncClient()

# ... (Pydantic Models and other functions are the same)

async def process_signal(signal: TradeSignal):
    """
    Main logic to process a signal, get a prediction, run risk checks,
    and execute a trade.
    """
    trade_id = str(uuid.uuid4())
    log_entry = {
        "trade_id": trade_id, "strategy": "baseline_v1", "instrument": signal.instrument,
        "timestamp": datetime.now(timezone.utc).isoformat(), "side": "PENDING", "quantity": 0.0,
        "price": 0.0, "execution_status": "RECEIVED", "prediction_id": None, "risk_flag": None
    }

    try:
        # 1. Check Global Kill-Switch using the shared client
        if await redis_client.is_killswitch_active():
            log_entry["execution_status"] = "REJECTED"
            log_entry["risk_flag"] = "GLOBAL_KILL_SWITCH"
            await log_trade(log_entry)
            logging.warning("Global kill-switch is active. Order rejected.")
            return

        # ... (rest of the function is the same)

    except Exception as e:
        logging.error(f"Failed to process signal: {e}")
        log_entry["execution_status"] = "ERROR"
        await log_trade(log_entry)

# ... (subscribe_to_signals is the same)

@app.on_event("startup")
async def startup_event():
    """On startup, initialize clients and start background tasks."""
    global redis_client
    redis_client = get_redis_client()
    asyncio.create_task(subscribe_to_signals())

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown, close client connections."""
    if redis_client:
        await redis_client.close()

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
