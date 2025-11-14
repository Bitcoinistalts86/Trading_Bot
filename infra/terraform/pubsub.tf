resource "google_pubsub_topic" "topics" {
  for_each = toset(var.pubsub_topics)
  name     = each.value
}

resource "google_pubsub_subscription" "dataflow_binance_sub" {
  name  = "dataflow-market-binance-raw-sub"
  topic = google_pubsub_topic.topics["market.binance.raw"].name
  ack_deadline_seconds = 60
}

resource "google_pubsub_subscription" "dataflow_uniswap_sub" {
  name  = "dataflow-market-uniswap-raw-sub"
  topic = google_pubsub_topic.topics["market.uniswap.raw"].name
  ack_deadline_seconds = 60
}
