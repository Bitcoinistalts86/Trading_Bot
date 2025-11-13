"""Minimal Binance websocket connector stub — reads WSS and publishes to Pub/Sub."""
import asyncio
import json
import os
import websockets

from google.cloud import pubsub_v1

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
TOPIC = os.environ.get("PUBSUB_TOPIC", "market.binance.ethusdt")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT, TOPIC)

async def listen():
    """Listens to the Binance websocket and publishes messages to Pub/Sub."""
    url = "wss://stream.binance.com:9443/ws/ethusdt@depth@100ms"
    async with websockets.connect(url) as ws:
        async for msg in ws:
            # Wrap and publish raw payload; downstream processors will normalize
            payload = json.dumps({
                "exchange": "binance",
                "instrument": "ETH/USDT",
                "ts": None,
                "payload": msg
            })
            publisher.publish(topic_path, payload.encode("utf-8"))

if __name__ == '__main__':
    asyncio.run(listen())
