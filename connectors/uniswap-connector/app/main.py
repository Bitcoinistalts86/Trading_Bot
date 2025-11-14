"""Uniswap connector — polls TheGraph for new swaps and publishes to Pub/Sub."""
import json
import logging
import os
import time
from datetime import datetime, timezone

import requests
from google.cloud import pubsub_v1

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
TOPIC_ID = os.environ.get("PUBSUB_TOPIC", "market.uniswap.raw")
THEGRAPH_URL = os.environ.get(
    "THEGRAPH_URL", "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
)
# Default to the WBTC-WETH 0.3% fee pool
PAIR_ID = os.environ.get("PAIR_ID", "0xcbcdf9626bc03e24f779434178a73a0b4bad62ed").lower()
POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", 60))

if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

# --- Pub/Sub Publisher ---
try:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    logging.info(f"Publisher initialized for topic: {topic_path}")
except Exception as e:
    logging.error(f"Failed to initialize Pub/Sub publisher: {e}")
    exit(1)

# --- TheGraph Query ---
# This query fetches the 100 most recent swaps for a given pool,
# ordered by timestamp in descending order.
SWAPS_QUERY = """
query GetSwaps($pair_id: ID!, $last_timestamp: BigInt!) {
  swaps(
    first: 100,
    where: { pool: $pair_id, timestamp_gt: $last_timestamp },
    orderBy: timestamp,
    orderDirection: asc
  ) {
    id
    transaction {
      id
    }
    timestamp
    token0 {
      symbol
    }
    token1 {
      symbol
    }
    amount0
    amount1
    amountUSD
    sender
    recipient
  }
}
"""

def normalize_message(swap: dict) -> dict:
    """
    Normalizes a raw swap object from TheGraph to the target BigQuery schema.
    """
    # Amounts can be positive (in) or negative (out)
    amount0 = float(swap['amount0'])
    amount1 = float(swap['amount1'])

    return {
        "transaction_hash": swap['transaction']['id'],
        "log_index": int(swap['id'].split('-')[-1]), # Extract log index from swap ID
        "exchange": "uniswap-v3",
        "pair": f"{swap['token0']['symbol']}-{swap['token1']['symbol']}",
        "timestamp": datetime.fromtimestamp(int(swap['timestamp']), tz=timezone.utc).isoformat(),
        "amount0_in": amount0 if amount0 > 0 else 0,
        "amount1_in": amount1 if amount1 > 0 else 0,
        "amount0_out": abs(amount0) if amount0 < 0 else 0,
        "amount1_out": abs(amount1) if amount1 < 0 else 0,
        "sender": swap['sender'],
        "to": swap['recipient'],
        "raw_message": json.dumps(swap)
    }


def poll_the_graph(last_timestamp: int):
    """
    Polls TheGraph for new swaps since the last timestamp.
    """
    try:
        variables = {"pair_id": PAIR_ID, "last_timestamp": str(last_timestamp)}
        response = requests.post(THEGRAPH_URL, json={'query': SWAPS_QUERY, 'variables': variables}, timeout=15)
        response.raise_for_status() # Raise an exception for bad status codes
        data = response.json()

        if 'errors' in data:
            logging.error(f"TheGraph API returned errors: {data['errors']}")
            return [], last_timestamp

        swaps = data.get('data', {}).get('swaps', [])
        if not swaps:
            logging.info("No new swaps found.")
            return [], last_timestamp

        new_last_timestamp = int(swaps[-1]['timestamp'])
        logging.info(f"Found {len(swaps)} new swaps. Newest timestamp: {new_last_timestamp}")
        return swaps, new_last_timestamp

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to query TheGraph: {e}")
        return [], last_timestamp


def main():
    """Main polling loop."""
    # Start polling for swaps from 10 minutes ago to avoid missing recent ones
    last_timestamp = int(time.time()) - 600
    logging.info(f"Starting Uniswap connector for pair {PAIR_ID}. Initial timestamp: {last_timestamp}")

    while True:
        swaps, new_timestamp = poll_the_graph(last_timestamp)

        for swap in swaps:
            try:
                normalized_msg = normalize_message(swap)
                future = publisher.publish(topic_path, json.dumps(normalized_msg).encode("utf-8"))
                future.result() # Wait for publish to complete
                logging.info(f"Published swap from transaction: {normalized_msg['transaction_hash']}")
            except Exception as e:
                logging.error(f"Failed to process or publish swap {swap.get('id', 'N/A')}: {e}")

        last_timestamp = new_timestamp
        logging.info(f"Sleeping for {POLL_INTERVAL_SECONDS} seconds...")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Connector stopped by user.")
    except Exception as e:
        logging.error(f"An unhandled error occurred in the main loop: {e}")

