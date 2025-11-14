# infra/terraform/redis.tf

# --- Google Cloud Memorystore for Redis ---
resource "google_redis_instance" "shared_state" {
  name           = "shared-state-redis"
  tier           = "BASIC" # Use BASIC for development/staging, STANDARD_HA for production
  memory_size_gb = 1
  location_id    = var.region # Deploy in the primary region
  auth_enabled   = false # Set to true and manage secrets for production

  # Connect to the default VPC network
  # For production, this should be a specific, shared VPC
  authorized_network = "default"

  connect_mode = "DIRECT_PEERING"
}
