resource "google_storage_bucket" "dataflow_templates" {
  name     = "${var.project_id}-dataflow-templates"
  location = var.region
  uniform_bucket_level_access = true
}

resource "google_service_account" "dataflow_sa" {
  account_id   = "dataflow-sa"
  display_name = "Dataflow service account for feature pipelines"
}

resource "google_project_iam_member" "dataflow_pubsub" {
  role   = "roles/pubsub.subscriber"
  member = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

resource "google_project_iam_member" "dataflow_bq" {
  role   = "roles/bigquery.dataEditor"
  member = "serviceAccount:${google_service_account.dataflow_sa.email}"
}

resource "google_pubsub_subscription" "feature_pipeline_sub" {
  name  = "sub-market-feature-ingest"
  topic = google_pubsub_topic.topics["market.binance.ethusdt"].name
  ack_deadline_seconds = 60
}

resource "google_bigquery_table" "features_ethusdt" {
  dataset_id = google_bigquery_dataset.ingest.dataset_id
  table_id   = "features_ethusdt"
  schema = <<EOF
[
  {"name":"exchange","type":"STRING"},
  {"name":"instrument","type":"STRING"},
  {"name":"ts","type":"TIMESTAMP"},
  {"name":"vwap_1s","type":"FLOAT"},
  {"name":"vwap_5s","type":"FLOAT"},
  {"name":"orderflow_imbalance","type":"FLOAT"},
  {"name":"bid_ask_spread","type":"FLOAT"},
  {"name":"payload","type":"STRING"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "ts"
  }
}
