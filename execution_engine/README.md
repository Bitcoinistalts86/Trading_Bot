# Execution Engine

The Execution Engine is a FastAPI service responsible for processing trading signals, performing risk checks, and routing orders. It serves as the final decision-making and execution layer in the trading pipeline.

## Key Features

-   **Signal Consumption:** Subscribes to a Pub/Sub topic (e.g., `signals.strategy`) to receive trading signals in real-time.
-   **Prediction Integration:** Calls the `model-gateway` service to fetch a live prediction for a given signal.
-   **Risk Management:** Implements critical pre-trade risk checks before executing any order.
-   **Global Kill-Switch:** Integrates with a central Redis instance to respect a global, real-time kill-switch. If the `global_kill_switch` key is set to `"true"` in Redis, all new orders are blocked.
-   **Smart Order Router (SOR):** Contains a simulated SOR that decides where and how to execute an order. Currently operates in `paper_trade` mode.
-   **Audit Logging:** Logs every received signal, risk check, and order execution decision to a `trade_logs` table in BigQuery for a complete audit trail.

## Pre-Trade Risk Checks

The following checks are performed before any order is sent to the SOR:

1.  **Global Kill-Switch:** Is the system-wide kill-switch active?
2.  **Max Order Size:** Does the order quantity exceed the configured `MAX_ORDER_SIZE`?
3.  **Max Volatility:** Does the instrument's current volatility (fetched from the feature store, simulated for now) exceed the `MAX_VOLATILITY` threshold?

If any check fails, the order is rejected, and the reason is logged to BigQuery.

## API Endpoints

-   `GET /health`: A standard health check endpoint. Returns `{"status": "ok"}`.

## Running Locally

1.  **Set Environment Variables:**
    ```bash
    export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    export REDIS_HOST="your-redis-host"
    export MODEL_GATEWAY_URL="http://localhost:8001" # Or the deployed URL
    export SIGNAL_SUBSCRIPTION="projects/your-gcp-project-id/subscriptions/signals.strategy"
    export BQ_TABLE_ID="your-gcp-project-id.features.trade_logs"
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Service:**
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8080
    ```

## Deployment

The service is automatically built and deployed to Cloud Run via the main `cloudbuild.yaml` file in the repository root. The Cloud Build pipeline injects the necessary production environment variables during deployment.
