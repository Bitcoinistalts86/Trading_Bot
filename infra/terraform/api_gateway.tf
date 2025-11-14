# infra/terraform/api_gateway.tf

# --- Service Account for the API Gateway ---
resource "google_service_account" "api_gateway_sa" {
  account_id   = "api-gateway-sa"
  display_name = "Service Account for the API Gateway"
}

# --- IAM Bindings for the API Gateway SA ---

# Allow the SA to be invoked as a Cloud Run service
resource "google_project_iam_member" "api_gateway_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}

# Allow the SA to subscribe to Pub/Sub for the WebSocket
resource "google_project_iam_member" "api_gateway_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}

# Allow the SA to connect to the Redis instance for state management
resource "google_project_iam_member" "api_gateway_redis_client" {
  project = var.project_id
  role    = "roles/redis.client"
  member  = "serviceAccount:${google_service_account.api_gateway_sa.email}"
}
