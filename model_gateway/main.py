# model_gateway/main.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import aiplatform
from typing import List

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
REGION = os.environ.get("REGION", "us-central1")
ENDPOINT_ID = os.environ.get("VERTEX_ENDPOINT_ID")

if not all([PROJECT_ID, REGION, ENDPOINT_ID]):
    raise ValueError("Missing required environment variables: GOOGLE_CLOUD_PROJECT, REGION, VERTEX_ENDPOINT_ID")

# --- FastAPI App ---
app = FastAPI(title="Model Gateway")

# --- Vertex AI Client ---
aiplatform.init(project=PROJECT_ID, location=REGION)
endpoint = aiplatform.Endpoint(ENDPOINT_ID)

# --- Pydantic Models ---
class PredictionInstance(BaseModel):
    mid_price: float
    volume_5s: float
    trade_imbalance_5s: float
    volatility_30s: float

class PredictionRequest(BaseModel):
    instances: List[PredictionInstance]

@app.post("/predict")
async def predict(request: PredictionRequest):
    """
    Accepts a list of instances and returns predictions from the Vertex AI Endpoint.
    """
    try:
        instances_list = [list(instance.dict().values()) for instance in request.instances]

        prediction = endpoint.predict(instances=instances_list)

        return prediction.predictions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
