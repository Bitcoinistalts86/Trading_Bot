# infra/terraform/secrets.tf

# --- Secret for JWT HMAC ---
# This resource defines the secret container in Secret Manager.
# The actual secret value (the version) is NOT managed by Terraform
# for security reasons and must be set manually in the GCP console or via gcloud.
resource "google_secret_manager_secret" "jwt_hmac_secret" {
  secret_id = "jwt-hmac-secret"

  replication {
    automatic = true
  }
}

# --- IAM Permissions for the API Gateway to access the secret ---
resource "google_secret_manager_secret_iam_member" "api_gateway_jwt_secret_accessor" {
  secret_id = google_secret_manager_secret.jwt_hmac_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:api-gateway-sa@${var.project_id}.iam.gserviceaccount.com"
}
