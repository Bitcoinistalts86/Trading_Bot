# examples/smoke_execution_engine.py
import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from google.cloud import pubsub_v1, bigquery
import redis

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
SIGNAL_TOPIC = "signals.strategy" # Topic the EE listens to
BQ_TABLE = f"{PROJECT_ID}.features.trade_logs"
REDIS_HOST = os.environ.get("REDIS_HOST") # Needs to be set
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
WAIT_TIME_SECONDS = 20
TEST_INSTRUMENT = "BTCUSDT"

if not all([PROJECT_ID, REDIS_HOST]):
    raise ValueError("GOOGLE_CLOUD_PROJECT and REDIS_HOST must be set.")

# --- Clients ---
publisher = pubsub_v1.PublisherClient()
bq_client = bigquery.Client()
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# --- Test Functions ---

def publish_mock_signal():
    """Publishes a mock signal to trigger the execution engine."""
    topic_path = publisher.topic_path(PROJECT_ID, SIGNAL_TOPIC)
    signal = {
        "instrument": TEST_INSTRUMENT,
        # In a real scenario, this would contain feature data for the model
    }
    future = publisher.publish(topic_path, json.dumps(signal).encode("utf-8"))
    future.result()
    print(f"Published mock signal for {TEST_INSTRUMENT} to {SIGNAL_TOPIC}")
    return signal

def verify_trade_log(start_time, expected_status, expected_flag=None):
    """Checks BigQuery for a trade log matching the test run."""
    print(f"\n--- Verifying BigQuery for status '{expected_status}'...")
    # Give BQ streaming inserts a moment
    time.sleep(15)

    query = f"""
        SELECT execution_status, risk_flag
        FROM `{BQ_TABLE}`
        WHERE timestamp >= TIMESTAMP_SECONDS({int(start_time)})
        AND instrument = '{TEST_INSTRUMENT}'
        ORDER BY timestamp DESC
        LIMIT 1
    """
    try:
        query_job = bq_client.query(query)
        results = list(query_job.result())

        if not results:
            print("❌ FAILED: No trade log found in BigQuery.")
            return False

        log = results[0]
        print(f"Found log: status='{log.execution_status}', risk_flag='{log.risk_flag}'")

        status_ok = log.execution_status == expected_status
        flag_ok = expected_flag is None or log.risk_flag == expected_flag

        if status_ok and flag_ok:
            print(f"✅ PASSED: Found expected log.")
            return True
        else:
            print(f"❌ FAILED: Log did not match expectations.")
            return False

    except Exception as e:
        print(f"An error occurred querying BigQuery: {e}")
        return False

def test_normal_execution():
    """Test Case 1: Happy path, signal is processed and simulated."""
    print("\n--- Test Case 1: Normal Signal Execution ---")
    start_time = time.time()
    publish_mock_signal()
    print(f"Waiting {WAIT_TIME_SECONDS}s for processing...")
    time.sleep(WAIT_TIME_SECONDS)
    return verify_trade_log(start_time, "SIMULATED_FILLED", "RISK_OK")

def test_kill_switch():
    """Test Case 2: Kill-switch is active, signal is rejected."""
    print("\n--- Test Case 2: Kill-Switch Engaged ---")

    # Activate kill-switch
    print("Activating global kill-switch in Redis...")
    redis_client.set("global_kill_switch", "true")

    start_time = time.time()
    publish_mock_signal()
    print(f"Waiting {WAIT_TIME_SECONDS}s for processing...")
    time.sleep(WAIT_TIME_SECONDS)
    success = verify_trade_log(start_time, "REJECTED", "GLOBAL_KILL_SWITCH")

    # Deactivate kill-switch
    print("Deactivating global kill-switch...")
    redis_client.delete("global_kill_switch")

    return success

def main():
    """Runs the full smoke test for the execution engine."""
    print("--- Starting Execution Engine Smoke Test ---")

    # Clear any old state
    redis_client.delete("global_kill_switch")

    normal_ok = test_normal_execution()
    kill_switch_ok = test_kill_switch()

    print("\n--- Smoke Test Summary ---")
    if normal_ok and kill_switch_ok:
        print("✅✅✅ All checks passed. The execution engine is working as expected.")
    else:
        print("❌❌❌ One or more checks failed.")

if __name__ == "__main__":
    main()
