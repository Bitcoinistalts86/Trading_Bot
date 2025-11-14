# --- GCS Bucket for Dataflow Templates ---
resource "google_storage_bucket" "dataflow_templates" {
  name     = "${var.project_id}-dataflow-templates"
  location = var.region
  uniform_bucket_level_access = true
}

# --- Dataflow Service Account ---
resource "google_service_account" "dataflow_sa" {
  account_id   = "dataflow-feature-engine-sa"
  display_name = "Dataflow service account for the feature engine pipeline"
}

# --- IAM Bindings for Dataflow Service Account ---

# Permission to consume from the raw data Pub/Sub topics
resource "google_project_iam_member" "dataflow_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

# Permission to publish to the real-time features Pub/Sub topic
resource "google_project_iam_member" "dataflow_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

# Permission to write to the BigQuery features table
resource "google_project_iam_member" "dataflow_bq_writer" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

# Permission for the Dataflow runner to manage its own jobs
resource "google_project_iam_member" "dataflow_worker" {
  project = var.project_id
  role   = "roles/dataflow.worker"
  member = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

# Permission for the Dataflow SA to read/write to the templates bucket
resource "google_project_iam_member" "dataflow_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.dataflow_sa.email}"
}
