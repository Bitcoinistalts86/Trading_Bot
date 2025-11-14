# infra/terraform/execution_engine.tf

# --- Service Account for the Execution Engine ---
resource "google_service_account" "execution_engine_sa" {
  account_id   = "execution-engine-sa"
  display_name = "Service Account for the Execution Engine"
}

# --- IAM Bindings for the Execution Engine SA ---

# Allow the SA to be invoked as a Cloud Run service
resource "google_project_iam_member" "execution_engine_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.execution_engine_sa.email}"
}

# Allow the SA to read from Pub/Sub topics (for signals)
resource "google_project_iam_member" "execution_engine_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.execution_engine_sa.email}"
}

# Allow the SA to write trade logs to BigQuery
resource "google_project_iam_member" "execution_engine_bq_writer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.execution_engine_sa.email}"
}

# Allow the SA to connect to the Redis instance
resource "google_project_iam_member" "execution_engine_redis_client" {
  project = var.project_id
  role    = "roles/redis.client"
  member  = "serviceAccount:${google_service_account.execution_engine_sa.email}"
}
