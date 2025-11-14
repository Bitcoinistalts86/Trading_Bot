# execution_engine/app/main.py
import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import httpx
import redis.asyncio as redis
from google.cloud import pubsub_v1, bigquery

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
REGION = os.environ.get("REGION", "us-central1")
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
MODEL_GATEWAY_URL = os.environ.get("MODEL_GATEWAY_URL") # e.g., http://model-gateway-service
SIGNAL_SUBSCRIPTION = os.environ.get("SIGNAL_SUBSCRIPTION") # e.g., projects/proj/subs/signals.strategy
BQ_TABLE_ID = os.environ.get("BQ_TABLE_ID") # e.g., proj.features.trade_logs

# --- Risk Management Configuration ---
MAX_ORDER_SIZE = 10.0 # Max quantity per order
MAX_VOLATILITY = 0.05 # Max 30s volatility

# --- Clients ---
app = FastAPI(title="Execution Engine")
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
bq_client = bigquery.Client()
http_client = httpx.AsyncClient()

# --- Pydantic Models ---
class TradeSignal(BaseModel):
    instrument: str
    # Add other signal fields as needed

class Order(BaseModel):
    trade_id: str
    strategy: str
    instrument: str
    side: str
    quantity: float
    price: float

# --- Core Logic ---

async def log_trade(trade_data: dict):
    """Logs a trade record to the BigQuery trade_logs table."""
    errors = bq_client.insert_rows_json(BQ_TABLE_ID, [trade_data])
    if errors:
        logging.error(f"Failed to insert rows to BigQuery: {errors}")

async def get_latest_features(instrument: str) -> dict:
    """
    Placeholder function to simulate fetching the latest features for an instrument.
    In a real implementation, this would query a real-time feature store (e.g., Redis, Vertex AI Feature Store).
    """
    # For simulation, we return a static, reasonable set of features.
    return {
        "mid_price": 50000.0,
        "volume_5s": 100.0,
        "trade_imbalance_5s": 10.0,
        "volatility_30s": 0.01
    }

async def pre_trade_risk_check(order: Order, features: dict) -> (bool, str):
    """Performs pre-trade risk checks."""
    if order.quantity > MAX_ORDER_SIZE:
        return False, "MAX_ORDER_SIZE_EXCEEDED"
    if features.get('volatility_30s', 0) > MAX_VOLATILITY:
        return False, "MAX_VOLATILITY_EXCEEDED"
    return True, "RISK_OK"

async def smart_order_router(order: Order, paper_trade: bool = True):
    """
    Simulated Smart Order Router. In a real system, this would connect
    to exchange APIs (e.g., CCXT) and manage order execution.
    """
    status = "SIMULATED_FILLED" if paper_trade else "LIVE_FILLED"
    logging.info(f"Executing order via SOR: {order.dict()} -> {status}")
    # In a real system, you would handle partial fills, errors, etc.
    return status

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
        # 1. Check Global Kill-Switch
        kill_switch = await redis_client.get("global_kill_switch")
        if kill_switch == "true":
            log_entry["execution_status"] = "REJECTED"
            log_entry["risk_flag"] = "GLOBAL_KILL_SWITCH"
            await log_trade(log_entry)
            logging.warning("Global kill-switch is active. Order rejected.")
            return

        # 2. Get Prediction from Model Gateway
        features = await get_latest_features(signal.instrument)
        if not MODEL_GATEWAY_URL:
            raise ValueError("MODEL_GATEWAY_URL is not set.")

        response = await http_client.post(
            f"{MODEL_GATEWAY_URL}/predict",
            json={"instances": [features]},
            timeout=10.0
        )
        response.raise_for_status()
        prediction_result = response.json()[0]
        prediction = {"prediction": prediction_result['prediction'], "id": response.headers.get("X-Request-ID", str(uuid.uuid4()))}
        log_entry["prediction_id"] = prediction["id"]

        # 3. Formulate Order
        order = Order(
            trade_id=trade_id, strategy="baseline_v1", instrument=signal.instrument,
            side="BUY" if prediction["prediction"] > 0.5 else "SELL",
            quantity=1.0, # Simplified quantity
            price=123.45 # Use latest price from feature store in a real system
        )
        log_entry.update(order.dict(include={"side", "quantity", "price"}))

        # 4. Pre-Trade Risk Checks
        is_safe, risk_flag = await pre_trade_risk_check(order, features)
        log_entry["risk_flag"] = risk_flag
        if not is_safe:
            log_entry["execution_status"] = "REJECTED"
            await log_trade(log_entry)
            logging.warning(f"Pre-trade risk check failed: {risk_flag}")
            return

        # 5. Execute via SOR
        execution_status = await smart_order_router(order, paper_trade=True)
        log_entry["execution_status"] = execution_status

        # 6. Final Log
        await log_trade(log_entry)
        logging.info(f"Successfully processed trade {trade_id}")

    except Exception as e:
        logging.error(f"Failed to process signal: {e}")
        log_entry["execution_status"] = "ERROR"
        await log_trade(log_entry)


async def subscribe_to_signals():
    """Background task to listen to the Pub/Sub subscription for new signals."""
    subscriber = pubsub_v1.SubscriberClient()

    def callback(message):
        try:
            signal = TradeSignal(**json.loads(message.data))
            logging.info(f"Received signal: {signal.instrument}")
            # Run the processing in the background to avoid blocking the subscriber
            asyncio.create_task(process_signal(signal))
        except Exception as e:
            logging.error(f"Failed to decode signal message: {e}")
        finally:
            message.ack()

    streaming_pull_future = subscriber.subscribe(SIGNAL_SUBSCRIPTION, callback=callback)
    logging.info(f"Listening for messages on {SIGNAL_SUBSCRIPTION}...")
    try:
        streaming_pull_future.result()
    except Exception as e:
        logging.error(f"Subscription listening failed: {e}")
        streaming_pull_future.cancel()

@app.on_event("startup")
async def startup_event():
    """On startup, create the background task for the Pub/Sub subscriber."""
    asyncio.create_task(subscribe_to_signals())

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
