"""
Binance websocket connector — reads two streams concurrently:
1. Trade stream (`@trade`) for executed trades.
2. Book Ticker stream (`@bookTicker`) for best bid/ask updates.

It enriches the trade messages with the latest bid/ask before publishing.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field

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

# --- Shared State for L1 Quote ---
@dataclass
class L1Quote:
    """Holds the latest Level 1 order book data."""
    best_bid: float = 0.0
    best_ask: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

# --- Pub/Sub Publisher ---
try:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    logging.info(f"Publisher initialized for topic: {topic_path}")
except Exception as e:
    logging.error(f"Failed to initialize Pub/Sub publisher: {e}")
    exit(1)


def normalize_message(msg: str, instrument: str, l1_quote: L1Quote) -> dict:
    """
    Normalizes a raw trade message from Binance and enriches it with L1 data.
    """
    raw = json.loads(msg)
    return {
        "trade_id": raw.get("t"),
        "exchange": "binance",
        "instrument": instrument.upper(),
        "timestamp": datetime.utcfromtimestamp(raw.get("T") / 1000).isoformat(),
        "price": float(raw.get("p")),
        "quantity": float(raw.get("q")),
        "side": "SELL" if raw.get("m") else "BUY",
        "best_bid": l1_quote.best_bid, # Enriched field
        "best_ask": l1_quote.best_ask, # Enriched field
        "raw_message": msg
    }


async def listen_trades(instrument: str, l1_quote: L1Quote):
    """Listens to the trade stream, enriches, and publishes."""
    url = f"wss://stream.binance.com:9443/ws/{instrument.lower()}@trade"
    logging.info(f"Connecting to trade stream: {url}")

    while True:
        try:
            async with websockets.connect(url) as ws:
                logging.info(f"Successfully connected to trade stream: {url}")
                while True:
                    msg = await ws.recv()
                    async with l1_quote.lock:
                        normalized_msg = normalize_message(msg, instrument, l1_quote)

                    future = publisher.publish(topic_path, json.dumps(normalized_msg).encode("utf-8"))
                    future.result()
                    logging.info(f"Published trade ID {normalized_msg['trade_id']} for {instrument}")
        except websockets.exceptions.ConnectionClosed:
            logging.warning("Trade stream connection closed. Reconnecting in 5s...")
        except Exception as e:
            logging.error(f"An error occurred in the trade listener: {e}")
        await asyncio.sleep(5)


async def listen_book_ticker(instrument: str, l1_quote: L1Quote):
    """Listens to the book ticker stream and updates the shared L1 quote."""
    url = f"wss://stream.binance.com:9443/ws/{instrument.lower()}@bookTicker"
    logging.info(f"Connecting to book ticker stream: {url}")

    while True:
        try:
            async with websockets.connect(url) as ws:
                logging.info(f"Successfully connected to book ticker stream: {url}")
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    async with l1_quote.lock:
                        l1_quote.best_bid = float(data['b'])
                        l1_quote.best_ask = float(data['a'])
                    logging.debug(f"Updated L1 quote for {instrument}: Bid={l1_quote.best_bid}, Ask={l1_quote.best_ask}")
        except websockets.exceptions.ConnectionClosed:
            logging.warning("Book ticker stream connection closed. Reconnecting in 5s...")
        except Exception as e:
            logging.error(f"An error occurred in the book ticker listener: {e}")
        await asyncio.sleep(5)


async def main():
    """Runs the concurrent listeners for trades and book tickers."""
    l1_quote = L1Quote()

    trade_task = asyncio.create_task(listen_trades(INSTRUMENT, l1_quote))
    book_ticker_task = asyncio.create_task(listen_book_ticker(INSTRUMENT, l1_quote))

    await asyncio.gather(trade_task, book_ticker_task)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Connector stopped by user.")
