"""A Cloud Run service that triggers a model retraining pipeline."""
import os
from fastapi import FastAPI
from google.cloud import pubsub_v1

app = FastAPI()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
TOPIC_ID = "model.retrain.trigger"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.post("/trigger")
async def trigger_retraining():
    """Publishes a message to the retraining topic."""
    # In a real implementation, this would be triggered by a monitoring system
    # that detects model drift or performance degradation.
    message = b"Retrain the model."
    future = publisher.publish(topic_path, message)
    return {"message": f"Published message {future.result()} to {topic_path}."}
