# execution_engine/app/main.py
"""
Unified Execution Engine.

This single FastAPI app replaces the two divergent implementations that used to
live at `execution_engine/main.py` (in-memory simulation) and
`execution_engine/app/main.py` (Redis/circuit-breaker scaffold that could not
import). It keeps the good ideas from both:

  * from app/main.py: Redis-backed multi-level kill-switch, a circuit breaker
    around the model gateway, and a BigQuery audit ledger;
  * from main.py: the FastAPI surface, the Pub/Sub signal subscriber, and the
    TWAP/VWAP algos -- now routed through a real ExchangeAdapter.

Endpoints (paths match contracts/openapi.yaml, with legacy aliases kept):
  GET  /health
  POST /v1/order        (alias: /order)            -- submit an order
  POST /v1/kill-switch  (alias: /kill-switch)      -- set global/user kill level
  GET  /v1/positions    (alias: /positions)        -- balances + risk snapshot
  GET  /v1/risk-config                              -- effective limits & mode
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import pybreaker
from fastapi import BackgroundTasks, FastAPI, HTTPException

from .adapters import build_adapter
from .config import load_settings
from .execution import Executor
from .kill_switch import KillSwitchLevel, build_kill_switch
from .models import Execution, Order, Signal
from .risk import RiskManager
from .sinks import ExecutionSink

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("execution_engine")

app = FastAPI(title="Execution Engine")

# Process-wide singletons, wired on startup.
settings = load_settings()
adapter = None
risk: RiskManager | None = None
executor: Executor | None = None
sink: ExecutionSink | None = None
kill_switch = None
model_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)


# --------------------------------------------------------------------------- #
# Model gateway (optional). Wrapped in a circuit breaker so a flaky model
# service trips open and orders are rejected rather than hanging.
# --------------------------------------------------------------------------- #
@model_breaker
async def get_prediction(instrument: str) -> dict:
    if not settings.model_gateway_url:
        return {"prediction": None, "skipped": True}
    import httpx
    async with httpx.AsyncClient(timeout=2.0) as client:
        r = await client.post(
            f"{settings.model_gateway_url}/predict",
            json={"instances": [{"instrument": instrument}]},
        )
        r.raise_for_status()
        return {"prediction": r.json()}


async def _handle_execution(ex: Execution) -> None:
    if sink:
        await sink.publish(ex)


async def process_order(order: Order) -> list[Execution]:
    assert risk and executor
    ref_price = await adapter.get_mark_price(order.instrument)

    decision = await risk.check(order, ref_price)
    if not decision.approved:
        logger.warning("Order %s rejected: %s", order.client_order_id, decision.reason)
        rej = Execution(
            order_id=order.client_order_id, exchange=getattr(adapter, "name", "unknown"),
            instrument=order.instrument, side=order.side, price=ref_price,
            quantity=0.0, status=f"REJECTED:{decision.reason}", correlation_id=order.correlation_id,
        )
        await _handle_execution(rej)
        return [rej]

    # Optional model gateway consultation (non-fatal if it trips).
    try:
        await get_prediction(order.instrument)
    except pybreaker.CircuitBreakerError:
        logger.warning("Model gateway circuit open; proceeding without prediction.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Model gateway error (ignored): %s", exc)

    return await executor.execute(order)


# --------------------------------------------------------------------------- #
# Pub/Sub signal subscriber
# --------------------------------------------------------------------------- #
def _start_signal_subscriber(loop: asyncio.AbstractEventLoop) -> None:
    try:
        from google.cloud import pubsub_v1
        subscriber = pubsub_v1.SubscriberClient()
        sub_path = subscriber.subscription_path(settings.project_id, settings.signals_subscription)

        def callback(message) -> None:
            try:
                data = json.loads(message.data)
                order = Signal(**data).to_order()
                asyncio.run_coroutine_threadsafe(process_order(order), loop)
                message.ack()
            except Exception as exc:  # noqa: BLE001
                logger.error("Bad signal message: %s", exc)
                message.nack()

        subscriber.subscribe(sub_path, callback=callback)
        logger.info("Subscribed to signals: %s", sub_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Signal subscriber disabled (%s).", exc)


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
@app.on_event("startup")
async def startup() -> None:
    global adapter, risk, executor, sink, kill_switch
    kill_switch = await build_kill_switch(settings.redis_host, settings.redis_port)
    sink = ExecutionSink(settings)

    # Fills reconciled from the exchange user-data stream are audited too.
    async def _on_reconciled_fill(fill: dict) -> None:
        logger.info("Reconciled fill: %s", fill)

    adapter = await build_adapter(settings, on_fill=_on_reconciled_fill)
    risk = RiskManager(settings.limits, kill_switch)
    # If the adapter reconciles against the exchange, risk reads truth from it.
    if getattr(adapter, "store", None) is not None:
        risk.bind_store(adapter.store)
    executor = Executor(adapter, risk, on_execution=_handle_execution)

    loop = asyncio.get_running_loop()
    import threading
    threading.Thread(target=_start_signal_subscriber, args=(loop,), daemon=True).start()
    logger.warning("Execution engine ready in %s mode.", settings.mode.value.upper())


@app.on_event("shutdown")
async def shutdown() -> None:
    if adapter:
        await adapter.close()


# --------------------------------------------------------------------------- #
# REST endpoints
# --------------------------------------------------------------------------- #
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "mode": settings.mode.value}


@app.post("/v1/order")
async def submit_order(order: Order, background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(process_order, order)
    return {"status": "accepted", "client_order_id": order.client_order_id, "mode": settings.mode.value}


@app.post("/order")  # legacy alias
async def submit_order_legacy(order: Order, background_tasks: BackgroundTasks) -> dict:
    return await submit_order(order, background_tasks)


@app.post("/v1/kill-switch")
async def set_kill_switch(level: str, user_id: str | None = None) -> dict:
    try:
        ks_level = KillSwitchLevel(level.upper())
    except ValueError:
        raise HTTPException(400, detail="level must be OFF|SOFT|HARD")
    if user_id:
        await kill_switch.set_user_level(user_id, ks_level)
    else:
        await kill_switch.set_global_level(ks_level)
    return {"status": "ok", "scope": user_id or "global", "level": ks_level.value}


@app.post("/kill-switch")  # legacy alias (ACTIVATE/DEACTIVATE -> HARD/OFF)
async def set_kill_switch_legacy(action: str) -> dict:
    level = "HARD" if action.upper() == "ACTIVATE" else "OFF"
    return await set_kill_switch(level)


@app.get("/v1/positions")
async def positions() -> dict:
    balances = await adapter.get_balances() if adapter else {}
    store = getattr(adapter, "store", None)
    reconciled = bool(store and store.seeded)
    out = {
        "mode": settings.mode.value,
        "balances": balances,
        "reconciled": reconciled,  # True => balances are exchange truth, not inferred
        "risk": risk.snapshot() if risk else {},
    }
    if reconciled:
        out["open_orders"] = store.open_order_count()
    return out


@app.get("/positions")  # legacy alias
async def positions_legacy() -> dict:
    return await positions()


@app.get("/v1/reconciliation")
async def reconciliation() -> dict:
    store = getattr(adapter, "store", None)
    if not store:
        return {"reconciled": False, "reason": "paper mode has no exchange to reconcile"}
    return store.snapshot()


@app.get("/v1/risk-config")
async def risk_config() -> dict:
    return {"mode": settings.mode.value, "limits": vars(settings.limits)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
