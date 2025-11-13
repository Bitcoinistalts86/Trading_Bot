resource "google_cloud_run_v2_service" "execution_engine" {
  name     = "execution-engine"
  location = var.region

  template {
    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/${var.artifact_registry}/execution-engine:latest"
    }
    service_account = google_service_account.connectors_sa.email
  }
}

resource "google_cloud_run_service_iam_binding" "execution_engine_invoker" {
  location = google_cloud_run_v2_service.execution_engine.location
  name     = google_cloud_run_v2_service.execution_engine.name
  role     = "roles/run.invoker"
  members = [
    "serviceAccount:${google_service_account.connectors_sa.email}",
    "serviceAccount:${google_service_account.dataflow_sa.email}",
  ]
}

resource "google_bigquery_table" "trade_logs" {
  dataset_id = google_bigquery_dataset.ingest.dataset_id
  table_id   = "trade_logs"

  schema = <<EOF
[
  {"name":"strategy_id","type":"STRING"},
  {"name":"instrument","type":"STRING"},
  {"name":"side","type":"STRING"},
  {"name":"price_target","type":"FLOAT"},
  {"name":"quantity","type":"FLOAT"},
  {"name":"order_type","type":"STRING"},
  {"name":"venue","type":"STRING"},
  {"name":"order_id","type":"STRING"},
  {"name":"timestamp","type":"TIMESTAMP"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "timestamp"
  }
}

resource "google_project_iam_member" "execution_engine_bq_writer" {
  role   = "roles/bigquery.dataEditor"
  member = "serviceAccount:${google_service_account.connectors_sa.email}"
}
