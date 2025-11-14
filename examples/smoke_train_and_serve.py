# examples/smoke_train_and_serve.py
import os
import time
from google.cloud import bigquery, aiplatform

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
BQ_LOCATION = "US"
PIPELINE_REGION = "us-central1"
PIPELINE_ROOT = f"gs://{PROJECT_ID}-models/pipeline_root"
PIPELINE_TEMPLATE_PATH = "train_pipeline.json"
MODEL_DISPLAY_NAME = "price-prediction-model"

if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set.")

# --- Clients ---
bq_client = bigquery.Client(project=PROJECT_ID)
aiplatform.init(project=PROJECT_ID, location=PIPELINE_REGION)

def run_bqml_baseline():
    """Runs the BQML baseline training and evaluation."""
    print("--- Running BQML Baseline ---")
    with open("../ml/bqml/create_baseline_model.sql", "r") as f:
        create_sql = f.read()
    with open("../ml/bqml/evaluate_baseline_model.sql", "r") as f:
        evaluate_sql = f.read()

    bq_client.query(create_sql).result()
    print("BQML model training complete.")

    query_job = bq_client.query(evaluate_sql)
    results = query_job.result()
    print("BQML model evaluation complete. Metrics stored in `model_metrics.bqml_baseline`.")
    return results.total_rows > 0

def run_vertex_pipeline():
    """Triggers the Vertex AI training pipeline and waits for it to complete."""
    print("\n--- Running Vertex AI Training Pipeline ---")

    pipeline_job = aiplatform.PipelineJob(
        display_name=MODEL_DISPLAY_NAME,
        template_path=PIPELINE_TEMPLATE_PATH,
        pipeline_root=PIPELINE_ROOT,
        parameter_values={
            'project': PROJECT_ID,
            'region': PIPELINE_REGION,
            'display_name': MODEL_DISPLAY_NAME,
            'gcs_output_path': f"gs://{PROJECT_ID}-models",
            'training_container_uri': f"us-central1-docker.pkg.dev/{PROJECT_ID}/ai-trading-artifacts/trainer:latest",
            'table_name': "features.features_intraday"
        }
    )
    pipeline_job.run()
    print(f"Vertex AI Pipeline started. Job ID: {pipeline_job.resource_name}")
    pipeline_job.wait() # Wait for the pipeline to finish

    if pipeline_job.state == aiplatform.gapic.JobState.JOB_STATE_SUCCEEDED:
        print("✅ Vertex AI Pipeline completed successfully.")
        return True
    else:
        print(f"❌ Vertex AI Pipeline failed with state: {pipeline_job.state}")
        return False

def test_model_endpoint():
    """Sends a sample prediction request to the newly deployed model."""
    print("\n--- Testing Model Endpoint ---")
    endpoints = aiplatform.Endpoint.list(filter=f'display_name="{MODEL_DISPLAY_NAME}"')
    if not endpoints:
        print("❌ No endpoint found for the model.")
        return False

    endpoint = endpoints[0]
    sample_instance = [
        {
            'mid_price': 50000.0,
            'volume_5s': 100.0,
            'trade_imbalance_5s': 10.0,
            'volatility_30s': 0.001
        }
    ]
    try:
        prediction = endpoint.predict(instances=sample_instance)
        print(f"Prediction response: {prediction}")
        if prediction.predictions:
            print("✅ Model endpoint test PASSED.")
            return True
        else:
            print("❌ Model endpoint test FAILED: No predictions returned.")
            return False
    except Exception as e:
        print(f"❌ Model endpoint test FAILED: {e}")
        return False

def main():
    """Runs the full smoke test for the ML lifecycle."""
    print("--- Starting ML Lifecycle Smoke Test ---")

    bqml_ok = run_bqml_baseline()
    pipeline_ok = run_vertex_pipeline()
    endpoint_ok = False
    if pipeline_ok:
        # Give the endpoint a moment to be ready after the pipeline finishes
        time.sleep(60)
        endpoint_ok = test_model_endpoint()

    print("\n--- Smoke Test Summary ---")
    if bqml_ok and pipeline_ok and endpoint_ok:
        print("✅✅✅ All ML lifecycle checks passed.")
    else:
        print("❌❌❌ One or more ML lifecycle checks failed.")

if __name__ == "__main__":
    main()
