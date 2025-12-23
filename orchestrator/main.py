# orchestrator/main.py
import asyncio
import logging
import os
import httpx
from fastapi import FastAPI, HTTPException, Depends
from httpx_retry import RetryTransport
from ..libraries.state.redis_state import get_redis_client, RedisStateClient
from ..libraries.state.kill_switch import get_kill_switch_client, KillSwitchClient, KillSwitchLevel
from ..libraries.observability import init_observability
from ..libraries.auth import get_current_admin_user, TokenData

# --- Configuration ---
API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL")
EXECUTION_ENGINE_URL = os.environ.get("EXECUTION_ENGINE_URL")
# Add other service URLs as needed

# --- FastAPI App ---
app = FastAPI(title="Orchestrator")
init_observability("orchestrator", app)
redis_client: RedisStateClient = None
kill_switch_client: KillSwitchClient = None
transport = RetryTransport(
    wrapped_transport=httpx.AsyncHTTPTransport(),
    max_attempts=3,
    backoff_factor=2,
    status_forcelist=[500, 502, 503, 504],
)
http_client = httpx.AsyncClient(transport=transport, timeout=10.0)

@app.on_event("startup")
async def startup_event():
    """On startup, initialize clients."""
    global redis_client, kill_switch_client
    redis_client = get_redis_client()
    kill_switch_client = get_kill_switch_client(redis_client.client)
    # Start background monitoring tasks
    asyncio.create_task(monitor_services())

@app.on_event("shutdown")
async def shutdown_event():
    """On shutdown, close client connections."""
    if redis_client:
        await redis_client.close()
    await http_client.aclose()

service_health_status = {}

async def check_service_health(service_name: str, url: str) -> bool:
    """Checks the health of a single service and updates the status."""
    try:
        response = await http_client.get(f"{url}/health")
        if response.status_code == 200:
            service_health_status[service_name] = "ok"
            return True
        else:
            service_health_status[service_name] = "down"
            return False
    except httpx.RequestError:
        service_health_status[service_name] = "down"
        return False

async def monitor_services():
    """Periodically checks the health of all critical services."""
    services_to_monitor = {
        "api_gateway": API_GATEWAY_URL,
        "execution_engine": EXECUTION_ENGINE_URL,
    }

    while True:
        is_api_gateway_ok = await check_service_health("api_gateway", services_to_monitor["api_gateway"])
        if not is_api_gateway_ok:
            logging.error("API Gateway is down! Activating HARD kill-switch.")
            await kill_switch_client.set_global_level(KillSwitchLevel.HARD)

        is_execution_engine_ok = await check_service_health("execution_engine", services_to_monitor["execution_engine"])
        if not is_execution_engine_ok:
            logging.error("Execution Engine is down! Activating SOFT kill-switch.")
            await kill_switch_client.set_global_level(KillSwitchLevel.SOFT)

        await asyncio.sleep(60)

# --- REST Endpoints ---
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/health/full", dependencies=[Depends(get_current_admin_user)])
async def full_health_check():
    """Returns the health status of all monitored services."""
    return service_health_status

@app.post("/orchestrator/restart/{service_name}", dependencies=[Depends(get_current_admin_user)])
async def restart_service(service_name: str):
    """(Placeholder) Triggers a restart of a given service."""
    # In a real K8s/Cloud Run setup, this would interact with the platform API
    logging.info(f"Restart requested for service: {service_name}")
    return {"status": "not_implemented", "service": service_name}

@app.get("/orchestrator/state", dependencies=[Depends(get_current_admin_user)])
async def get_orchestrator_state():
    """Returns the current state of the orchestrator and the system."""
    kill_switch_level = await kill_switch_client.get_global_level()
    return {
        "kill_switch_level": kill_switch_level.value,
        "monitored_services": {
            "api_gateway": API_GATEWAY_URL,
            "execution_engine": EXECUTION_ENGINE_URL,
        }
    }
