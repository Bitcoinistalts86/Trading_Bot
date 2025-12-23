# api_gateway/app/pubsub_consumer.py
import asyncio
import logging
import os
from google.cloud import pubsub_v1

from .websocket_router import ConnectionManager, broadcast_to_clients

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
SUBSCRIPTION_ID = os.environ.get("FEATURES_SUBSCRIPTION_ID") # e.g., "features-realtime-sub"

async def start_pubsub_listener(manager: ConnectionManager):
    """
    Creates a Pub/Sub subscriber and listens for messages in the background,
    broadcasting them to all connected WebSocket clients.
    """
    if not PROJECT_ID or not SUBSCRIPTION_ID:
        logging.error("Pub/Sub project or subscription ID not configured. WebSocket consumer will not start.")
        return

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    async def callback(message):
        """Callback executed for each received message."""
        try:
            logging.debug(f"Received message from Pub/Sub: {message.data}")
            await broadcast_to_clients(manager, message.data.decode("utf-8"))
        except Exception as e:
            logging.error(f"Error processing Pub/Sub message: {e}")
        finally:
            message.ack()

    # The subscriber runs in a separate thread managed by the client library.
    # We just need to start it.
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
    logging.info(f"Listening for messages on {subscription_path}...")

    try:
        # Keep the listener alive. In a real app, you might handle cancellation.
        await asyncio.Future()
    except asyncio.CancelledError:
        streaming_pull_future.cancel()
        logging.info("Pub/Sub listener has been stopped.")
