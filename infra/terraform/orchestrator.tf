# infra/terraform/orchestrator.tf

resource "google_cloud_run_v2_service" "orchestrator" {
  name     = "orchestrator"
  location = var.region
  project  = var.project_id

  template {
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/${var.artifact_repository}/orchestrator:latest"
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
        name  = "API_GATEWAY_URL"
        value = google_cloud_run_v2_service.api_gateway.uri
      }
      env {
        name  = "EXECUTION_ENGINE_URL"
        value = google_cloud_run_v2_service.execution_engine.uri
      }
      env {
        name  = "REDIS_HOST"
        value = google_redis_instance.default.host
      }
      env {
        name  = "REDIS_PORT"
        value = google_redis_instance.default.port
      }
    }
  }
}

resource "google_cloud_run_service_iam_member" "orchestrator_invoker" {
  location = google_cloud_run_v2_service.orchestrator.location
  project  = google_cloud_run_v2_service.orchestrator.project
  service  = google_cloud_run_v2_service.orchestrator.name
  role     = "roles/run.invoker"
  member   = "allUsers" # Or a more restrictive principal
}
