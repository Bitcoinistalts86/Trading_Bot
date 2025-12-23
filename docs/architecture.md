# System Architecture

This document contains the architecture diagrams for the AI Trading & Arbitrage Platform.

## High-Level Architecture

This diagram shows the flow of data and control from ingestion to execution and the user interface.

```mermaid
graph TD
    subgraph "External Markets"
        direction LR
        CEX[CEXs]
        DeX[DeXs]
        Trad[Traditional]
    end

    subgraph "Data & Feature Pipelines"
        direction TB
        Connectors[connectors]
        Dataflow[data_pipeline/beam_feature_pipeline]
    end

    subgraph "Model Lifecycle"
        direction TB
        BQML[ml/bqml]
        Training[model_pipeline]
        Retraining[retraining_trigger]
    end

    subgraph "Trading & Execution"
        direction TB
        Execution[execution_engine]
    end

    subgraph "GCP Infrastructure"
        direction LR

    subgraph "Data Stores"
        direction TB
        TSDB[BigQuery]
        ModelRegistry[Vertex AI Model Registry]
    end

    %% Connections
    External_Markets -- "Raw Market Data" --> Connectors
    Connectors -- "Normalized Data (Pub/Sub)" --> Dataflow
    Dataflow -- "Features" --> TSDB

    TSDB -- "Training Data" --> BQML
    TSDB -- "Training Data" --> Training
    Training -- "Trained Models" --> ModelRegistry
    ModelRegistry -- "Models" --> Execution

    Retraining -- "Trigger (Pub/Sub)" --> Training

    Execution -- "Trade Orders" --> Connectors

    Web -- "User Actions" --> API
    Mobile -- "User Actions" --> API
    API -- "Commands & Queries" --> Execution
    API -- "Commands & Queries" --> Training

    Execution -- "Live P&L, Risk" --> API
    API -- "Data" --> Web
    API -- "Data" --> Mobile
```
