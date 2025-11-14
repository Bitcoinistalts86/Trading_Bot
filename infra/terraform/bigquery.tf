resource "google_bigquery_dataset" "market_data" {
  dataset_id = "market_data"
  location   = var.location
  description = "Market data for the AI trading platform"
}

resource "google_bigquery_table" "binance_trades" {
  dataset_id = google_bigquery_dataset.market_data.dataset_id
  table_id   = "binance_trades"

  schema = <<EOF
[
  {"name": "trade_id", "type": "INTEGER", "mode": "NULLABLE"},
  {"name": "exchange", "type": "STRING", "mode": "REQUIRED"},
  {"name": "instrument", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "price", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "quantity", "type": "FLOAT", "mode": "REQUIRED"},
  {"name": "side", "type": "STRING", "mode": "REQUIRED"},
  {"name": "raw_message", "type": "STRING", "mode": "NULLABLE"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "timestamp"
  }
}

resource "google_bigquery_table" "uniswap_swaps" {
  dataset_id = google_bigquery_dataset.market_data.dataset_id
  table_id   = "uniswap_swaps"

  schema = <<EOF
[
  {"name": "transaction_hash", "type": "STRING", "mode": "REQUIRED"},
  {"name": "log_index", "type": "INTEGER", "mode": "REQUIRED"},
  {"name": "exchange", "type": "STRING", "mode": "REQUIRED"},
  {"name": "pair", "type": "STRING", "mode": "REQUIRED"},
  {"name": "timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
  {"name": "amount0_in", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "amount1_in", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "amount0_out", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "amount1_out", "type": "FLOAT", "mode": "NULLABLE"},
  {"name": "sender", "type": "STRING", "mode": "NULLABLE"},
  {"name": "to", "type": "STRING", "mode": "NULLABLE"},
  {"name": "raw_message", "type": "STRING", "mode": "NULLABLE"}
]
EOF

  time_partitioning {
    type = "DAY"
    field = "timestamp"
  }
}
