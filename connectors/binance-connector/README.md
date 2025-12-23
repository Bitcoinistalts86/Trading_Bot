# Binance Connector

This connector subscribes to the Binance WebSocket trade feed for a specified instrument, normalizes the data, and publishes it to a Google Cloud Pub/Sub topic.

## Data Schema

The connector normalizes the raw Binance trade data into the following JSON schema, which matches the `binance_trades` table in BigQuery:

```json
{
  "trade_id": 123456789,
  "exchange": "binance",
  "instrument": "BTCUSDT",
  "timestamp": "2025-11-14T12:00:00.000Z",
  "price": 50000.00,
  "quantity": 0.1,
  "side": "BUY",
  "raw_message": "{...}"
}
```

## Running Locally

1.  **Authenticate with Google Cloud:**
    ```bash
    gcloud auth application-default login
    ```

2.  **Set environment variables:**
    ```bash
    export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    export PUBSUB_TOPIC="market.binance.raw"
    export INSTRUMENT="btcusdt" # e.g., ethusdt, solusdt
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the connector:**
    ```bash
    python main.py
    ```

## Deployment

The connector is designed to be deployed as a Cloud Run service. The `../../cloudbuild.yaml` file is configured to build the Docker image and deploy it.

To deploy using Cloud Build, run the following command from the repository root:

```bash
gcloud builds submit --config cloudbuild.yaml . \
  --substitutions=PROJECT_ID="your-gcp-project-id"
```

You can override the default instrument by modifying the `_BINANCE_INSTRUMENT` substitution variable in the `cloudbuild.yaml` file or by passing it in the `gcloud` command.
