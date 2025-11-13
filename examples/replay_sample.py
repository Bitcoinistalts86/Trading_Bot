"""Simple example showing how to replay messages into Pub/Sub for testing."""
import time
from google.cloud import pubsub_v1

PROJECT = "your-project"
TOPIC = "market.binance.ethusdt"
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT, TOPIC)

with open('examples/sample_ticks.jsonl', 'r', encoding='utf-8') as fh:
    for line in fh:
        publisher.publish(topic_path, line.encode('utf-8'))
        time.sleep(0.01)
