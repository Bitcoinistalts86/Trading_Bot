"""The execution engine for the AI Trading & Arbitrage Platform."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from google.cloud import bigquery

app = FastAPI()

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
BIGQUERY_DATASET = "trading_ingest"
BIGQUERY_TABLE = "trade_logs"

# --- In-memory State (for simulation) ---
STATE = {
    "kill_switch_activated": False,
    "portfolio": {"USD": 100000.0, "ETH": 0.0},
    "open_orders": {},
}

# --- BigQuery Client ---
bq_client = bigquery.Client(project=PROJECT_ID)

class Signal(BaseModel):
    """Represents a trading signal."""
    strategy_id: str
    instrument: str
    side: str  # "BUY" or "SELL"
    price_target: float
    quantity: float
    order_type: str  # "MARKET" or "LIMIT"
    pass

# --- Simulated Logic ---

def smart_order_router(signal: Signal) -> str:
    """Selects the best venue based on simulated liquidity and fees."""
    print("SOR: Analyzing liquidity and fees...")
    if signal.instrument == "ETH/USDT":
        if signal.quantity > 10:
            return "binance"
        return "uniswap"
    return "binance"

def check_risk(signal: Signal) -> bool:
    """Performs pre-trade risk checks."""
    if signal.instrument == "ETH/USDT" and signal.quantity > 50:
        print("RISK CHECK FAILED: Order quantity exceeds max position size.")
        return False
    required_capital = signal.price_target * signal.quantity
    if signal.side == "BUY" and STATE["portfolio"]["USD"] < required_capital:
        print("RISK CHECK FAILED: Insufficient capital.")
        return False
    print("RISK CHECK PASSED")
    return True

def execute_on_binance(signal: Signal) -> str:
    """Simulates placing an order on Binance."""
    print(f"Executing on Binance: {signal.side} {signal.quantity} {signal.instrument}")
    order_id = f"binance-{uuid.uuid4()}"
    STATE["open_orders"][order_id] = signal
    if signal.side == "BUY":
        STATE["portfolio"]["USD"] -= signal.price_target * signal.quantity
        STATE["portfolio"]["ETH"] += signal.quantity
    else:
        STATE["portfolio"]["USD"] += signal.price_target * signal.quantity
        STATE["portfolio"]["ETH"] -= signal.quantity
    return order_id

def execute_on_uniswap(signal: Signal) -> str:
    """Simulates placing an order on Uniswap."""
    print(f"Executing on Uniswap: {signal.side} {signal.quantity} {signal.instrument}")
    order_id = f"uniswap-{uuid.uuid4()}"
    STATE["open_orders"][order_id] = signal
    if signal.side == "BUY":
        STATE["portfolio"]["USD"] -= signal.price_target * signal.quantity
        STATE["portfolio"]["ETH"] += signal.quantity
    else:
        STATE["portfolio"]["USD"] += signal.price_target * signal.quantity
        STATE["portfolio"]["ETH"] -= signal.quantity
    return order_id

def log_trade(signal: Signal, venue: str, order_id: str):
    """Logs a trade to BigQuery."""
    rows_to_insert = [{"strategy_id": signal.strategy_id, "instrument": signal.instrument, "side": signal.side, "price_target": signal.price_target, "quantity": signal.quantity, "order_type": signal.order_type, "venue": venue, "order_id": order_id, "timestamp": datetime.now(timezone.utc).isoformat()}]
    errors = bq_client.insert_rows_json(f"{PROJECT_ID}.{BIGQUERY_DATASET}.{BIGQUERY_TABLE}", rows_to_insert)
    if errors:
        print(f"Encountered errors while inserting rows: {errors}")

async def process_trade(signal: Signal):
    """The main trade processing and execution flow."""
    if STATE["kill_switch_activated"]:
        print("Trade rejected: Kill switch is active.")
        return

    print(f"--- Processing new signal: {signal.strategy_id} ---")
    if not check_risk(signal):
        return
    venue = smart_order_router(signal)
    if venue == "binance":
        order_id = execute_on_binance(signal)
    elif venue == "uniswap":
        order_id = execute_on_uniswap(signal)
    else:
        print(f"Unknown venue: {venue}")
        return
    log_trade(signal, venue, order_id)
    print(f"--- Trade processed. Order ID: {order_id} ---")
    print(f"Current Portfolio: {STATE['portfolio']}")

# --- API Endpoints ---

@app.post("/signal")
async def receive_signal(signal: Signal, background_tasks: BackgroundTasks):
    """Receives a trading signal and executes the trade in the background."""
    background_tasks.add_task(process_trade, signal)
    return {"message": "Signal received and is being processed."}

@app.post("/kill-switch/activate")
async def activate_kill_switch():
    """Activates the kill-switch, halting all new trades."""
    STATE["kill_switch_activated"] = True
    print("!!! KILL SWITCH ACTIVATED !!! All new trades will be rejected.")
    print(f"Cancelling {len(STATE['open_orders'])} open orders...")
    STATE["open_orders"].clear()
    return {"message": "Kill switch activated. All new trades halted and open orders cancelled."}

@app.post("/kill-switch/deactivate")
async def deactivate_kill_switch():
    """Deactivates the kill-switch, resuming normal trading."""
    STATE["kill_switch_activated"] = False
    print(">>> Kill switch deactivated. Trading resumed. <<<")
    return {"message": "Kill switch deactivated. Trading can resume."}
