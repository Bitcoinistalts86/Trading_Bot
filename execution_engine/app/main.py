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
import pybreaker

# Import the shared Redis client
from ..libraries.state.redis_state import get_redis_client, RedisStateClient
from ..libraries.state.kill_switch import get_kill_switch_client, KillSwitchClient, KillSwitchLevel
from ..libraries.observability import init_observability

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
# ... (rest of configuration is the same)

# --- Clients ---
app = FastAPI(title="Execution Engine")
init_observability("execution_engine", app)
redis_client: RedisStateClient = None # Will be initialized on startup
kill_switch_client: KillSwitchClient = None
model_gateway_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)
bq_client = bigquery.Client()
http_client = httpx.AsyncClient()

class TradeSignal(BaseModel):
    instrument: str
    side: str
    quantity: float
    correlation_id: str = None

# ... (rest of pydantic models and other functions are the same)

async def process_signal(signal: TradeSignal):
    """
    Main logic to process a signal, get a prediction, run risk checks,
    and execute a trade.
    """
    trade_id = str(uuid.uuid4())
    log_entry = {
        "trade_id": trade_id, "strategy": "baseline_v1", "instrument": signal.instrument,
        "timestamp": datetime.now(timezone.utc).isoformat(), "side": "PENDING", "quantity": 0.0,
        "price": 0.0, "execution_status": "RECEIVED", "prediction_id": None, "risk_flag": None,
        "correlation_id": signal.correlation_id
    }

    try:
        # 1. Check Global Kill-Switch using the shared client
        if await kill_switch_client.is_hard_kill_active():
            logging.critical("HARD kill-switch active. Halting signal processing.")
            # By raising an exception, we ensure the message is not ACK'd and will be redelivered.
            raise HTTPException(status_code=503, detail="HARD kill-switch is active.")

        if await kill_switch_client.is_soft_kill_active():
            log_entry["execution_status"] = "REJECTED"
            log_entry["risk_flag"] = "GLOBAL_KILL_SWITCH"
            await log_trade(log_entry)
            logging.warning("Global kill-switch is active. Order rejected.")
            return

        # 2. Get Prediction from Model Gateway
        @model_gateway_breaker
        async def get_prediction(instrument: str):
            # In a real implementation, this would call the model gateway
            # For now, we'll just simulate a successful call
            return {"prediction_id": str(uuid.uuid4()), "prediction": 0.6}

        try:
            prediction_result = await get_prediction(signal.instrument)
            log_entry["prediction_id"] = prediction_result["prediction_id"]
        except pybreaker.CircuitBreakerError:
            log_entry["execution_status"] = "REJECTED"
            log_entry["risk_flag"] = "MODEL_GATEWAY_UNAVAILABLE"
            await log_trade(log_entry)
            logging.warning("Model gateway is unavailable. Order rejected.")
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
    global redis_client, kill_switch_client
    redis_client = get_redis_client()
    kill_switch_client = get_kill_switch_client(redis_client.client)
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
