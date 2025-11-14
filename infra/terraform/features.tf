# --- BigQuery Dataset for Features ---
resource "google_bigquery_dataset" "features" {
  dataset_id = "features"
  location   = var.location
  description = "Dataset for storing computed trading features"
}

# --- BigQuery Table for Intraday Features ---
resource "google_bigquery_table" "features_intraday" {
  dataset_id = google_bigquery_dataset.features.dataset_id
  table_id   = "features_intraday"

  schema = <<EOF
[
  {"name": "instrument", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "mid_price", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "spread", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "volume_1s", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "volume_5s", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "trade_imbalance_5s", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "volatility_30s", "type": "FLOAT", "mode": "NULLABLE"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "timestamp"
  }
}

# --- BigQuery Table for Trade Logs ---
resource "google_bigquery_table" "trade_logs" {
  dataset_id = google_bigquery_dataset.features.dataset_id
  table_id   = "trade_logs"

  schema = <<EOF
[
  {"name": "trade_id", "type": "STRING", "mode": "REQUIRED"},
  {"name": "strategy", "type": "STRING", "mode": "NULLABLE"},
  {"name": "instrument", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "side", "type": "STRING", "mode": "REQUIRED"},
  {"name": "quantity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "price", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "execution_status", "type": "STRING", "mode": "REQUIRED"},
  {"name": "prediction_id", "type": "STRING", "mode": "NULLABLE"},
  {"name": "risk_flag", "type": "STRING", "mode": "NULLABLE"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "timestamp"
  }
}
