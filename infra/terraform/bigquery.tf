resource "google_bigquery_dataset" "ingest" {
  dataset_id = "trading_ingest"
  location   = var.location
  description = "Ingested market data for trading platform"
  default_table_expiration_ms = null
}

resource "google_bigquery_table" "raw_ticks" {
  dataset_id = google_bigquery_dataset.ingest.dataset_id
  table_id   = "raw_ticks"

  schema = <<EOF
[
  {"name":"exchange","type":"STRING"},
  {"name":"instrument","type":"STRING"},
  {"name":"ts","type":"TIMESTAMP"},
  {"name":"payload","type":"STRING"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "ts"
  }
}
