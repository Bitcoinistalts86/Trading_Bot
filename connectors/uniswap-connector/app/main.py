"""Minimal Uniswap connector — connects to an Ethereum node and publishes new blocks to Pub/Sub."""
import asyncio
import json
import os
from web3 import Web3
from websockets.exceptions import ConnectionClosed

from google.cloud import pubsub_v1

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT")
TOPIC = os.environ.get("PUBSUB_TOPIC", "market.uniswap.ethusdt")
INFURA_WSS_URL = os.environ.get(
    "INFURA_WSS_URL", "wss://mainnet.infura.io/ws/v3/YOUR_INFURA_PROJECT_ID"
)


publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT, TOPIC)

async def listen():
    """Connects to an Ethereum node, subscribes to new blocks, and publishes them to Pub/Sub."""
    w3 = Web3(Web3.WebsocketProvider(INFURA_WSS_URL))
    subscription_id = await w3.eth.subscribe('newHeads')

    print(f"Subscribed to new blocks with subscription ID: {subscription_id}")

    while True:
        try:
            message = await asyncio.wait_for(subscription_id.get(), timeout=60)
            block = w3.eth.get_block(message['result']['hash'])
            payload = json.dumps({
                "exchange": "uniswap",
                "instrument": "ETH/USDT", # This is a placeholder
                "ts": block.timestamp,
                "payload": w3.to_json(block)
            })
            publisher.publish(topic_path, payload.encode("utf-8"))
            print(f"Published block {block.number} to Pub/Sub.")
        except asyncio.TimeoutError:
            print("No new block in 60 seconds. Reconnecting...")
            subscription_id = await w3.eth.subscribe('newHeads') # Resubscribe
        except ConnectionClosed:
            print("Connection closed. Reconnecting...")
            w3 = Web3(Web3.WebsocketProvider(INFURA_WSS_URL))
            subscription_id = await w3.eth.subscribe('newHeads')
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break


if __name__ == '__main__':
    # Note: You need to set GOOGLE_APPLICATION_CREDENTIALS and INFURA_WSS_URL
    if "YOUR_INFURA_PROJECT_ID" in INFURA_WSS_URL:
        print("Error: Please set the INFURA_WSS_URL environment variable.")
    else:
        asyncio.run(listen())
