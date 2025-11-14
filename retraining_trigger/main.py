# retraining_trigger/main.py
import os
from fastapi import FastAPI, HTTPException
from google.cloud import pubsub_v1

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
TOPIC_ID = "model.retrain.trigger"

if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set.")

# --- FastAPI App ---
app = FastAPI(title="Retraining Trigger")

# --- Pub/Sub Publisher ---
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@app.post("/trigger")
async def trigger_retraining():
    """
    Publishes a message to the model.retrain.trigger topic.
    """
    try:
        # The message can contain parameters for the pipeline
        message = {"data": "retrain", "timestamp": str(os.path.getpid())}
        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        future.result()
        return {"status": "ok", "message": f"Published message to {TOPIC_ID}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
