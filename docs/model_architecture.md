# Model Architecture

This document outlines the hybrid model architecture for the AI Trading & Arbitrage Platform, combining the rapid prototyping capabilities of BigQueryML with the production-grade power of Vertex AI.

## Architecture Diagram

```mermaid
flowchart LR
  subgraph Ingest
    A[Binance Connector] -->|Pub/Sub| B[Pub/Sub Topics]
    C[Uniswap Connector] -->|Pub/Sub| B
  end

  B --> D[Dataflow (Beam) Feature Pipeline]
  D --> E[BigQuery: Feature Tables]
  D --> F[Featurestore Batch Import]
  F --> G[Vertex Feature Store (Online)]

  E --> H[BigQueryML Models / Notebooks]
  G --> I[Vertex AI Endpoints (Online Models)]
  E --> J[Vertex AI Training (Vertex Pipelines)]
  J --> I
  I --> K[Execution Engine (Cloud Run) - calls for inference]
  K --> L[Exchanges / Wallets]

  subgraph Monitoring
    M[Vertex Model Monitoring] --> J
    N[Cloud Monitoring & Logging] --> K
  end
```

## Components

-   **BigQueryML:** Used for rapid prototyping and baseline model creation directly in BigQuery using SQL. This allows for quick iteration on feature ideas and model types.
-   **Vertex AI:** The production ML platform, used for:
    -   **Training:** Custom training jobs and Vertex AI Pipelines for complex models (TensorFlow, PyTorch, RL).
    -   **Serving:** Low-latency model serving via Vertex AI Endpoints.
    -   **Monitoring:** Model and feature drift detection to trigger retraining.
    -   **Feature Store:** A centralized repository for sharing features between training and serving.
