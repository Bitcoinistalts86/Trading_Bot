"""Binance websocket connector — reads WSS and publishes to Pub/Sub."""
import asyncio
import json
import logging
import os
from datetime import datetime

import websockets
from google.cloud import pubsub_v1

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
TOPIC_ID = os.environ.get("PUBSUB_TOPIC", "market.binance.raw")
INSTRUMENT = os.environ.get("INSTRUMENT", "btcusdt") # Default to BTC/USDT

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


def normalize_message(msg: str, instrument: str) -> dict:
    """
    Normalizes a raw trade message from Binance to the target BigQuery schema.
    """
    raw = json.loads(msg)

    # See Binance documentation for trade stream payload:
    # https://binance-docs.github.io/apidocs/spot/en/#trade-streams
    return {
        "trade_id": raw.get("t"),
        "exchange": "binance",
        "instrument": instrument.upper(),
        "timestamp": datetime.utcfromtimestamp(raw.get("T") / 1000).isoformat(),
        "price": float(raw.get("p")),
        "quantity": float(raw.get("q")),
        "side": "SELL" if raw.get("m") else "BUY",
        "raw_message": msg # Keep the original message for auditing
    }


async def listen(instrument: str):
    """
    Connects to the Binance websocket, normalizes messages, and publishes them.
    """
    # Use the trade stream, not the depth stream
    url = f"wss://stream.binance.com:9443/ws/{instrument.lower()}@trade"
    logging.info(f"Connecting to Binance WebSocket: {url}")

    try:
        async with websockets.connect(url) as ws:
            logging.info(f"Successfully connected to {url}")
            while True:
                try:
                    msg = await ws.recv()
                    normalized_msg = normalize_message(msg, instrument)

                    # Publish to Pub/Sub
                    future = publisher.publish(topic_path, json.dumps(normalized_msg).encode("utf-8"))
                    future.result() # Wait for publish to complete

                    logging.info(f"Published trade ID {normalized_msg['trade_id']} for {instrument}")

                except websockets.exceptions.ConnectionClosed:
                    logging.warning("WebSocket connection closed. Reconnecting...")
                    break
                except Exception as e:
                    logging.error(f"An error occurred while processing a message: {e}")
                    # In a production system, you might want a more robust reconnection logic
                    await asyncio.sleep(5)

    except Exception as e:
        logging.error(f"Failed to connect to WebSocket: {e}")


async def main():
    """Main function to run the listener."""
    while True:
        await listen(INSTRUMENT)
        logging.info("Reconnecting in 10 seconds...")
        await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Connector stopped by user.")
