# chaos_tests/test_execution_engine_fault.py
import asyncio
import httpx
import os
from unittest.mock import patch, AsyncMock
import pytest

# This test assumes the orchestrator code is available for import
# and that we can patch its dependencies.
from orchestrator.main import monitor_services, service_health_status, KillSwitchLevel

@pytest.mark.asyncio
@patch('orchestrator.main.http_client', new_callable=AsyncMock)
@patch('orchestrator.main.kill_switch_client', new_callable=AsyncMock)
async def test_execution_engine_fault(mock_kill_switch, mock_http_client):
    """
    Simulates an execution_engine fault by patching the http_client in the
    orchestrator to raise a RequestError.
    """
    print("--- Running Chaos Test: Execution Engine Fault ---")

    # 1. Configure Mocks
    # The first health check to the api_gateway should succeed.
    # The second health check to the execution_engine should fail.
    mock_http_client.get.side_effect = [
        httpx.Response(200, json={"status": "ok"}),
        httpx.RequestError("Execution engine is down")
    ]

    # 2. Run the monitoring loop once
    # We need to wrap the async generator in a task and then cancel it
    # to prevent it from running forever.
    monitoring_task = asyncio.create_task(monitor_services())
    await asyncio.sleep(1) # Allow the task to run one iteration
    monitoring_task.cancel()

    # 3. Verify the outcome
    assert service_health_status["execution_engine"] == "down"
    mock_kill_switch.set_level.assert_called_with(KillSwitchLevel.SOFT)

    print("SUCCESS: Orchestrator correctly handled the execution engine fault.")
    print("--- Chaos Test: Execution Engine Fault Complete ---")

if __name__ == "__main__":
    # This test would be run with pytest, not as a standalone script.
    print("This script is intended to be run with pytest and the appropriate mocks.")
