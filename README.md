# AI Trading & Arbitrage Platform

This repository contains the source code for a production-grade AI trading and arbitrage platform. It is designed to be a multi-agent system, with each agent responsible for a specific component of the platform.

## Global Objectives

1.  **Build a low-latency, reliable trading platform** with continuous model updates.
2.  **Provide web (Next.js) + mobile (Flutter) UI** exposing real-time PnL, strategy controls, backtester and kill-switch.
3.  **Start with Binance (CEX) + Uniswap V3 (DeX) + one traditional market** (e.g., FX via OANDA) as minimum viable connectors.
4.  **Decision latency target: <100 ms** from event to order submission (document measurement method).
5.  **Provide full CI/CD, infra-as-code, monitoring, model lifecycle, and paper-trading safety gates.**

## Workspace Structure

The workspace is organized into a set of specialized agents, each with its own directory and responsibilities. The `workspace/manifest.yaml` file provides a detailed overview of the agents and their interfaces.

-   `api_gateway/`: Backend / API Agent
-   `contracts/`: API contracts (OpenAPI, Protobuf)
-   `data_pipeline/`: Data Agent
-   `docs/`: Architecture diagrams, latency budgets, risk policies
-   `examples/`: Scripts for paper trading and data replay
-   `execution_engine/`: Execution Agent
-   `features/`: Feature & Feature Store Agent
-   `frontend/`: Frontend Agent (Web)
-   `infra/`: DevOps / Infra Agent
-   `mobile/`: Frontend Agent (Mobile)
-   `model_pipeline/`: Model Agent (Vertex AI)
-   `qa/`: QA / Ops Agent
-   `security/`: Security & Compliance Agent
-   `workspace/`: Orchestrator agent files

## Documentation

-   [Technology Stack & Data Structures](docs/technology_stack.md)
-   [Project Setup Guide](docs/setup_guide.md)
-   [Architecture Diagrams](docs/architecture.md)

## Milestone 2: Feature & Model Pipelines

This milestone adds a streaming feature pipeline using Dataflow and scaffolds the hybrid model training architecture with BigQueryML and Vertex AI.

-   **[Model Architecture](docs/model_architecture.md)**

## Milestone 3: Model Training & Continuous Learning

This milestone scaffolds the model training and continuous learning pipelines using Vertex AI.

-   **[Training Guide](docs/training_guide.md)**

## Milestone 4: Execution Engine & Smart Order Router

This milestone adds the execution engine, which is responsible for receiving trading signals, routing orders, and managing risk.

-   **[Execution & Risk Control](docs/execution_guide.md)**

## Milestone 1 Quickstart

This milestone provisions the initial data ingestion pipeline for Binance and Uniswap data into BigQuery.

### Prerequisites

-   gcloud CLI authenticated and project set
-   Docker installed (for local builds)
-   Terraform v1.x
-   Cloud Build enabled and Artifact Registry created

### 1) Configure env vars
```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export ARTIFACT_REPOSITORY=ai-trading-artifacts
```

### 2) Deploy infra (local)
```bash
./scripts/deploy_tf.sh
```

### 3) Build & deploy via Cloud Build
```bash
gcloud builds submit --config cloudbuild.yaml --substitutions=_ARTIFACT_REPOSITORY=${ARTIFACT_REPOSITORY}
```

### 4) Run connectors locally
```bash
./scripts/local_run.sh
```

### 5) Replay sample data
```bash
python examples/replay_sample.py
```

## Getting Started

### Prerequisites

-   Google Cloud SDK
-   Terraform
-   Docker
-   Node.js
-   Python

### Deployment

1.  **Initialize Terraform:**
    ```bash
    cd infra
    terraform init
    terraform apply
    ```

2.  **Deploy services:**
    ```bash
    gcloud builds submit --config cloudbuild.yaml .
    ```

## Communication & Interfaces

Communication between agents is primarily handled through Pub/Sub topics and REST endpoints.

### Pub/Sub Topics

-   `market.{exchange}.{instrument}`: Raw market data
-   `features.{instrument}`: Real-time features
-   `signals.{strategy}`: Trading signals
-   `orders.{exchange}`: Order events
-   `exec.{order_lifecycle}`: Execution traces

### REST Endpoints

-   `POST /v1/signal`: Accepts a trading signal.
-   `POST /v1/order`: Submits an order to the execution gateway.
-   `POST /v1/kill-switch`: Activates the emergency kill-switch.

## Safety Guards

-   **Paper-first:** New strategies must run in paper trading mode before live deployment.
-   **Human-in-loop:** Significant changes to trading logic require operator approval.
-   **Kill-Switch:** A global kill-switch is available to halt all trading activity.
-   **Audit:** All trades are logged to an immutable ledger in BigQuery.
