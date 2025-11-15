# infra/terraform/auth.tf

resource "google_service_account" "auth_service_sa" {
  account_id   = "auth-service-sa"
  display_name = "Authentication Service Account"
  project      = var.project_id
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "jwt-hmac-secret"
  project   = var.project_id

  replication {
    automatic = true
  }
}

resource "google_cloud_run_v2_service" "auth_service" {
  name     = "auth-service"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.auth_service_sa.email

    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/${var.artifact_repository}/auth-service:latest"
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name = "JWT_SECRET_ID"
        value = google_secret_manager_secret.jwt_secret.secret_id
      }
       env {
        name = "BQ_DATASET_ID"
        value = google_bigquery_dataset.users.dataset_id
      }
       env {
        name = "BQ_TABLE_ID"
        value = google_bigquery_table.auth_accounts.table_id
      }
    }
  }
}

resource "google_cloud_run_service_iam_member" "auth_service_invoker" {
  location = google_cloud_run_v2_service.auth_service.location
  project  = google_cloud_run_v2_service.auth_service.project
  service  = google_cloud_run_v2_service.auth_service.name
  role     = "roles/run.invoker"
  member   = "allUsers" # For simplicity in this milestone
}

resource "google_project_iam_member" "auth_service_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.auth_service_sa.email}"
}

resource "google_project_iam_member" "auth_service_bq_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.auth_service_sa.email}"
}
