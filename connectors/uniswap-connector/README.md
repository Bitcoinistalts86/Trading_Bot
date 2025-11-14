# Uniswap Connector

This connector polls TheGraph's Uniswap v3 subgraph for a specified pair, normalizes the swap data, and publishes it to a Google Cloud Pub/Sub topic.

## Data Schema

The connector normalizes the raw Uniswap swap data from TheGraph into the following JSON schema, which matches the `uniswap_swaps` table in BigQuery:

```json
{
  "transaction_hash": "0x...",
  "log_index": 123,
  "exchange": "uniswap-v3",
  "pair": "WBTC-WETH",
  "timestamp": "2025-11-14T12:00:00.000Z",
  "amount0_in": 1.0,
  "amount1_in": 0.0,
  "amount0_out": 0.0,
  "amount1_out": 20.0,
  "sender": "0x...",
  "to": "0x...",
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
    export PUBSUB_TOPIC="market.uniswap.raw"
    export PAIR_ID="0xcbcdf9626bc03e24f779434178a73a0b4bad62ed" # WBTC-WETH 0.3%
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

You can override the default pair by modifying the `_UNISWAP_PAIR_ID` substitution variable in the `cloudbuild.yaml` file or by passing it in the `gcloud` command.
