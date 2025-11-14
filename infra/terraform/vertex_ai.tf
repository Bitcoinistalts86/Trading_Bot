# infra/terraform/vertex_ai.tf

# --- GCS Bucket for Model Artifacts ---
resource "google_storage_bucket" "models" {
  name          = "${var.project_id}-models"
  location      = var.location # Use the same location as BigQuery datasets
  uniform_bucket_level_access = true
  force_destroy = false # Set to true in non-prod environments if needed
}

# --- Service Account for Vertex AI Pipelines ---
resource "google_service_account" "vertex_pipelines_sa" {
  account_id   = "vertex-pipelines-sa"
  display_name = "Service Account for Vertex AI Pipelines"
}

# --- IAM Bindings for the Vertex AI Pipeline SA ---

# Allow the SA to run Vertex AI Custom Jobs and Pipelines
resource "google_project_iam_member" "vertex_sa_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.vertex_pipelines_sa.email}"
}

# Allow the SA to read data from BigQuery
resource "google_project_iam_member" "vertex_sa_bigquery_reader" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.vertex_pipelines_sa.email}"
}

# Allow the SA to read and write model artifacts to the GCS bucket
resource "google_storage_bucket_iam_member" "vertex_sa_model_bucket_admin" {
  bucket = google_storage_bucket.models.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.vertex_pipelines_sa.email}"
}

# Allow the SA to act as a service account for other services it creates
resource "google_project_iam_member" "vertex_sa_iam_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.vertex_pipelines_sa.email}"
}

# Allow the SA to publish messages (e.g., for monitoring or notifications)
resource "google_project_iam_member" "vertex_sa_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.vertex_pipelines_sa.email}"
}
