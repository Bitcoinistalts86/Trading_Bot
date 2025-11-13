resource "google_cloud_run_v2_service" "retraining_trigger" {
  name     = "retraining-trigger"
  location = var.region

  template {
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/${var.artifact_registry}/retraining-trigger:latest"
    }
    service_account = google_service_account.connectors_sa.email
  }
}

resource "google_cloud_run_service_iam_binding" "retraining_trigger_invoker" {
  location = google_cloud_run_v2_service.retraining_trigger.location
  name     = google_cloud_run_v2_service.retraining_trigger.name
  role     = "roles/run.invoker"
  members = [
    "allUsers", # For simplicity in this skeleton; restrict in production
  ]
}

resource "google_project_iam_member" "retraining_trigger_pubsub_publisher" {
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.connectors_sa.email}"
}
