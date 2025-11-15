# infra/terraform/bq_users.tf

resource "google_bigquery_dataset" "users" {
  dataset_id = "users"
  project    = var.project_id
  location   = var.region
}

resource "google_bigquery_table" "auth_accounts" {
  dataset_id = google_bigquery_dataset.users.dataset_id
  table_id   = "auth_accounts"
  project    = var.project_id

  schema = <<EOF
[
  {
    "name": "user_id",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Unique identifier for the user"
  },
  {
    "name": "email",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "User's email address"
  },
  {
    "name": "password_hash",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "Hashed password"
  },
  {
    "name": "role",
    "type": "STRING",
    "mode": "REQUIRED",
    "description": "User role (USER or ADMIN)"
  },
  {
    "name": "created_at",
    "type": "TIMESTAMP",
    "mode": "REQUIRED",
    "description": "Timestamp of account creation"
  },
  {
    "name": "last_login_at",
    "type": "TIMESTAMP",
    "mode": "NULLABLE",
    "description": "Timestamp of last login"
  }
]
EOF
}
