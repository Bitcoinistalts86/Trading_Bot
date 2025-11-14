#!/bin/bash
# scripts/deploy_gateway.sh

# This script deploys the model gateway to Cloud Run.
# It dynamically finds the latest Vertex AI Endpoint and injects its ID
# as an environment variable into the gateway service.

set -e

# --- Configuration ---
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="model-gateway"
IMAGE_NAME="us-central1-docker.pkg.dev/${PROJECT_ID}/ai-trading-artifacts/model-gateway:latest"
MODEL_DISPLAY_NAME="price-prediction-model"
SERVICE_ACCOUNT="vertex-pipelines-sa@${PROJECT_ID}.iam.gserviceaccount.com"

echo "--- Deploying Model Gateway ---"
echo "Project ID: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service Name: ${SERVICE_NAME}"

# 1. Find the latest active Vertex AI Endpoint for the model
echo "Finding latest Vertex AI Endpoint for model: ${MODEL_DISPLAY_NAME}..."
ENDPOINT_ID=$(gcloud ai endpoints list \
  --region=${REGION} \
  --filter="displayName=${MODEL_DISPLAY_NAME}" \
  --format="value(name)" \
  --sort-by="~createTime" \
  --limit=1)

if [ -z "${ENDPOINT_ID}" ]; then
  echo "❌ Error: No active endpoint found for model '${MODEL_DISPLAY_NAME}'."
  exit 1
fi

echo "✅ Found Endpoint ID: ${ENDPOINT_ID}"

# 2. Deploy the gateway to Cloud Run with the correct Endpoint ID
echo "Deploying Cloud Run service: ${SERVICE_NAME}..."
gcloud run deploy ${SERVICE_NAME} \
  --image=${IMAGE_NAME} \
  --platform=managed \
  --region=${REGION} \
  --no-allow-unauthenticated \
  --service-account=${SERVICE_ACCOUNT} \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},REGION=${REGION},VERTEX_ENDPOINT_ID=${ENDPOINT_ID}"

echo "✅ Deployment complete."
