# System Architecture

This document contains the architecture diagrams for the AI Trading & Arbitrage Platform.

## High-Level Architecture

This diagram shows the flow of data and control from ingestion to execution and the user interface.

```mermaid
graph TD
    subgraph "External Markets"
        direction TB
        Binance[Binance]
        Uniswap[Uniswap]
    end

    subgraph "GCP Infrastructure"
        direction LR

        subgraph "Data & Features"
            Binance -- Trades & L1 Book --> A[Connectors (Cloud Run)]
            Uniswap -- Swaps --> A
            A -- Raw Data --> B(Pub/Sub: market.*)
            B --> C[Dataflow Feature Pipeline]
            C -- Streaming Inserts --> D((BigQuery: features_intraday))
            C -- Real-time Features --> E(Pub/Sub: features.realtime)
        end

        subgraph "MLOps & Training"
            D -- Training Data --> F[Vertex AI Pipeline]
            F -- Registers --> G[Vertex AI Model Registry]
            G -- Deploys --> H[Vertex AI Endpoint]
            I(Pub/Sub: model.retrain.trigger) -- Triggers --> F
            J[Retraining Trigger (Cloud Run)] -- Publishes --> I
        end

        subgraph "Serving & Execution"
            K[API Gateway (Cloud Run)] -- HTTP Request --> L[Model Gateway (Cloud Run)]
            L -- Prediction --> H
            K -- WebSocket Stream --> M[Frontend (Cloud Run)]
            E -- Pushes Features --> K

            N(Pub/Sub: signals.strategy) -- Pushes Signals --> O[Execution Engine (Cloud Run)]
            O -- Fetches Prediction --> L
            O -- Checks Kill-Switch --> P((Redis: Shared State))
            O -- Logs Trades --> Q((BigQuery: trade_logs))
            O -- Simulated Orders --> S[Exchange Simulators]
        end

        subgraph "User Interface"
             M -- User Actions --> K
             K -- Kill-Switch Control --> P
        end
    end

    style A fill:#cce5ff,stroke:#333,stroke-width:2px
    style C fill:#cce5ff,stroke:#333,stroke-width:2px
    style F fill:#d5e8d4,stroke:#333,stroke-width:2px
    style O fill:#ffcc99,stroke:#333,stroke-width:2px
    style M fill:#f8cecc,stroke:#333,stroke-width:2px
```
