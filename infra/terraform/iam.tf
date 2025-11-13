resource "google_service_account" "connectors_sa" {
  account_id   = "connectors-sa"
  display_name = "Service account for connectors and cloud run"
}

# Grant pubsub publisher to connectors SA
resource "google_project_iam_member" "pubsub_publisher" {
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.connectors_sa.email}"
}

# BigQuery writer
resource "google_project_iam_member" "bq_data_editor" {
  role   = "roles/bigquery.dataEditor"
  member = "serviceAccount:${google_service_account.connectors_sa.email}"
}

# Cloud Run Invoker will be granted to Cloud Build later
