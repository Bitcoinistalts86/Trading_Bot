# Model Architecture

This document outlines the hybrid model architecture for the AI Trading & Arbitrage Platform, combining the rapid prototyping capabilities of BigQueryML with the production-grade power of Vertex AI.

## Architecture Diagram
```mermaid
graph TD
    subgraph Data Ingestion
        A[Binance Connector] -- Raw Trades --> B(Pub/Sub: market.binance.raw)
        C[Uniswap Connector] -- Raw Swaps --> D(Pub/Sub: market.uniswap.raw)
    end
    subgraph Feature Engineering
        B --> E[Dataflow Feature Pipeline]
        D --> E
        E -- Streaming Inserts --> F((BigQuery: features_intraday))
        E -- Real-time Features --> G(Pub/Sub: features.realtime)
    end
    subgraph "Training & Serving"
        F -- Training Data --> H[Vertex AI Training Pipeline]
        H -- Registers Model --> I[Vertex AI Model Registry]
        I -- Deploys Model --> J[Vertex AI Endpoint]
        K[Model Gateway] -- Prediction Request --> J
    end
    subgraph Retraining
        L(Pub/Sub: model.retrain.trigger) -- Triggers --> H
        M[Retraining Trigger Service] -- Manual Trigger --> L
        N[Model Monitoring] -- Future: Drift Detection --> L
    end
    style F fill:#f9f,stroke:#333,stroke-width:2px
    style I fill:#ccf,stroke:#333,stroke-width:2px
end
```

## Components
- **BigQueryML:** Used for rapid prototyping and baseline model creation directly in BigQuery using SQL.
- **Vertex AI:** The production ML platform, used for:
    - **Training:** A custom training job containerizes a TensorFlow model. A Vertex AI Pipeline (`train_pipeline.py`) orchestrates the training, evaluation, and registration of this model.
    - **Serving:** The trained model is automatically deployed to a low-latency Vertex AI Endpoint.
    - **Model Registry:** Serves as the central repository for versioned, production-ready models.

## Deployment Process

The deployment is a multi-stage process orchestrated by Cloud Build and manual scripts.

1.  **CI/CD Pipeline (`cloudbuild.yaml`):** On a merge to the `main` branch, the following automated steps occur:
    *   All service container images (connectors, trainer, gateway, trigger) are built and pushed to Artifact Registry.
    *   The Vertex AI training pipeline is compiled and submitted. This pipeline trains the model and creates/updates the Vertex AI Endpoint.
    *   The `retraining_trigger` service is deployed to Cloud Run.

2.  **Model Gateway Deployment (`scripts/deploy_gateway.sh`):** The `model-gateway` service is **not** deployed automatically by the main CI/CD pipeline. This is because it has a runtime dependency on the Vertex AI Endpoint, which is created dynamically by the training pipeline.
    *   **To deploy or update the gateway:** An operator must run the `scripts/deploy_gateway.sh` script **after** the Vertex AI training pipeline has successfully completed and the endpoint is active.
    *   This script automatically finds the latest active endpoint ID and injects it as an environment variable into the Cloud Run service during deployment.

## Retraining Policy & Automation
- **Trigger:** The `model.retrain.trigger` Pub/Sub topic is the central trigger for launching a new training pipeline run.
- **Automation:**
    1.  A Cloud Run service (`retraining_trigger`) provides a manual endpoint to publish a message to the trigger topic.
    2.  The main Vertex AI training pipeline can be configured to be triggered by messages on this topic (this is a manual configuration step in the Cloud Console or via `gcloud`).

## Model Promotion & Rollback
- **Promotion:** The current pipeline deploys to a single `price-prediction-model` endpoint. For a production setup, a separate `production` endpoint should be created. Promotion would involve running the `ModelDeployOp` step of the pipeline (or a separate pipeline) targeting the production endpoint with a specific, validated model version from the Model Registry.
- **Rollback:** Vertex AI Endpoints support traffic splitting. To roll back a model, an operator can manually redeploy a previous, known-good model version from the Model Registry to the production endpoint.
