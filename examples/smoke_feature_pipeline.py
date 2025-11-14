# examples/smoke_feature_pipeline.py
import json
import os
import time
from datetime import datetime, timezone
from google.cloud import pubsub_v1, bigquery

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
BINANCE_INPUT_TOPIC = "market.binance.raw"
UNISWAP_INPUT_TOPIC = "market.uniswap.raw"
FEATURES_OUTPUT_TOPIC = "features.realtime"
BQ_TABLE = f"{PROJECT_ID}.features.features_intraday"
WAIT_TIME_SECONDS = 30
TEST_INSTRUMENT_BINANCE = "BTCUSDT"
TEST_INSTRUMENT_UNISWAP = "WBTC-WETH"

if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set.")

# --- Clients ---
publisher = pubsub_v1.PublisherClient()
subscriber = pubsub_v1.SubscriberClient()
bq_client = bigquery.Client()

# --- Sample Data ---
SAMPLE_BINANCE_TRADE = {
    "trade_id": 999999999,
    "exchange": "binance",
    "instrument": TEST_INSTRUMENT_BINANCE,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "price": 50000.0,
    "quantity": 0.01,
    "side": "BUY",
    "best_bid": 49999.5,
    "best_ask": 50000.5,
    "raw_message": "{}"
}
SAMPLE_UNISWAP_SWAP = {
    "transaction_hash": "0xsmoketest" + str(int(time.time())),
    "log_index": 1,
    "exchange": "uniswap-v3",
    "pair": TEST_INSTRUMENT_UNISWAP,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "amount0_in": 1.0,
    "amount1_in": 0.0,
    "amount0_out": 0.0,
    "amount1_out": 20.0,
    "sender": "0xsmoke",
    "to": "0xtest",
    "raw_message": "{}"
}

def publish_sample_data():
    """Publishes one sample message to each input topic."""
    binance_topic_path = publisher.topic_path(PROJECT_ID, BINANCE_INPUT_TOPIC)
    uniswap_topic_path = publisher.topic_path(PROJECT_ID, UNISWAP_INPUT_TOPIC)

    publisher.publish(binance_topic_path, json.dumps(SAMPLE_BINANCE_TRADE).encode("utf-8"))
    print(f"Published sample trade to {BINANCE_INPUT_TOPIC}")

    publisher.publish(uniswap_topic_path, json.dumps(SAMPLE_UNISWAP_SWAP).encode("utf-8"))
    print(f"Published sample swap to {UNISWAP_INPUT_TOPIC}")

def verify_bigquery(start_time):
    """Checks BigQuery for new feature rows since the test started."""
    print(f"\n--- Verifying BigQuery Table: {BQ_TABLE} ---")
    query = f"""
        SELECT COUNT(*) as count
        FROM `{BQ_TABLE}`
        WHERE timestamp >= TIMESTAMP_SECONDS({int(start_time)})
        AND (instrument = '{TEST_INSTRUMENT_BINANCE}' OR instrument = '{TEST_INSTRUMENT_UNISWAP}')
    """
    try:
        query_job = bq_client.query(query)
        results = query_job.result()
        for row in results:
            count = row.count
            print(f"Found {count} new row(s) in BigQuery.")
            if count > 0:
                print("✅ BigQuery verification PASSED.")
                return True
            else:
                print("❌ BigQuery verification FAILED.")
                return False
    except Exception as e:
        print(f"An error occurred querying BigQuery: {e}")
        print("❌ BigQuery verification FAILED.")
        return False

def verify_pubsub(start_time):
    """Checks the output Pub/Sub topic for new messages."""
    print(f"\n--- Verifying Pub/Sub Topic: {FEATURES_OUTPUT_TOPIC} ---")
    subscription_path = subscriber.subscription_path(PROJECT_ID, "smoke_test_sub") # Assumes this sub exists

    try:
        # Create a temporary subscription to pull messages
        subscriber.create_subscription(name=subscription_path, topic=publisher.topic_path(PROJECT_ID, FEATURES_OUTPUT_TOPIC))
    except Exception:
        # Subscription likely already exists, which is fine.
        pass

    try:
        response = subscriber.pull(subscription=subscription_path, max_messages=10, timeout=10)

        count = 0
        for msg in response.received_messages:
            data = json.loads(msg.message.data)
            msg_ts = dateparser.parse(data['timestamp']).timestamp()
            if msg_ts >= start_time:
                count += 1
            subscriber.acknowledge(subscription=subscription_path, ack_ids=[msg.ack_id])

        print(f"Found {count} new message(s) in Pub/Sub.")
        if count > 0:
            print("✅ Pub/Sub verification PASSED.")
            return True
        else:
            print("❌ Pub/Sub verification FAILED.")
            return False
    except Exception as e:
        print(f"An error occurred pulling from Pub/Sub: {e}")
        print("❌ Pub/Sub verification FAILED.")
        return False
    finally:
        # Clean up the temporary subscription
        subscriber.delete_subscription(subscription=subscription_path)


def main():
    """Runs the smoke test."""
    print("--- Starting Feature Pipeline Smoke Test ---")
    start_time = time.time()

    publish_sample_data()

    print(f"\nWaiting {WAIT_TIME_SECONDS} seconds for the pipeline to process...")
    time.sleep(WAIT_TIME_SECONDS)

    bq_success = verify_bigquery(start_time)
    pubsub_success = verify_pubsub(start_time)

    print("\n--- Smoke Test Summary ---")
    if bq_success and pubsub_success:
        print("✅✅✅ All checks passed. The feature pipeline is working end-to-end.")
    else:
        print("❌❌❌ One or more checks failed.")

if __name__ == "__main__":
    main()
