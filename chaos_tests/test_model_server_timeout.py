# chaos_tests/test_model_server_timeout.py
import asyncio
import httpx
from unittest.mock import patch, AsyncMock
import os
import pytest
import random
import uuid
from google.cloud import bigquery
from opentelemetry import trace

# This test assumes the execution_engine code is available for import
# and that we can patch its dependencies. This would be run in a
# local test environment.
from execution_engine.app.main import process_signal, TradeSignal

# --- Configuration ---
EXECUTION_ENGINE_URL = os.environ.get("EXECUTION_ENGINE_URL")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

# --- Mocks ---
class MockBigQueryClient:
    def __init__(self):
        self.logged_trades = []
    def insert_rows_json(self, table, rows):
        self.logged_trades.extend(rows)

@pytest.mark.asyncio
@patch('execution_engine.app.main.http_client', new_callable=AsyncMock)
@patch('execution_engine.app.main.bq_client', new_callable=MockBigQueryClient)
@patch('execution_engine.app.main.kill_switch_client', new_callable=AsyncMock)
async def test_model_server_timeout(mock_kill_switch, mock_bq_client, mock_http_client):
    """
    Simulates a model server timeout by patching the httpx client in the
    execution_engine to raise a TimeoutException.
    """
    print("--- Running Chaos Test: Model Server Timeout ---")

    # Use a deterministic random seed
    random.seed(0)

    # 1. Configure Mocks
    mock_http_client.post.side_effect = httpx.TimeoutException("Model gateway timed out")
    mock_kill_switch.is_soft_kill_active.return_value = False
    mock_kill_switch.is_hard_kill_active.return_value = False

    # 2. Create a sample signal with a correlation ID
    correlation_id = str(uuid.uuid4())
    signal = TradeSignal(instrument="BTC/USD", side="buy", quantity=1, correlation_id=correlation_id)

    # 3. Process the signal within a trace span
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("chaos-test-model-timeout") as span:
        span.set_attribute("correlation_id", correlation_id)
        await process_signal(signal)

    # 4. Verify the outcome
    assert len(mock_bq_client.logged_trades) == 1
    log_entry = mock_bq_client.logged_trades[0]
    assert log_entry["execution_status"] == "REJECTED"
    assert log_entry["risk_flag"] == "MODEL_GATEWAY_UNAVAILABLE"
    assert log_entry["correlation_id"] == correlation_id

    # 5. Log structured failure artifact (placeholder)
    print(f"CHAOS_ARTIFACT: {{'test': 'model_server_timeout', 'correlation_id': '{correlation_id}', 'outcome': 'success'}}")

    print("SUCCESS: Execution engine correctly handled the model gateway timeout.")
    print("--- Chaos Test: Model Server Timeout Complete ---")

if __name__ == "__main__":
    # This test would be run with pytest, not as a standalone script.
    print("This script is intended to be run with pytest and the appropriate mocks.")
