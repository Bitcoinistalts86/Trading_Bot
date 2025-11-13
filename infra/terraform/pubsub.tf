resource "google_pubsub_topic" "topics" {
  for_each = toset(var.pubsub_topics)
  name     = each.value
}

resource "google_pubsub_subscription" "connectors_sub" {
  for_each = toset(var.pubsub_topics)
  name  = "sub-${each.value}"
  topic = google_pubsub_topic.topics[each.value].name
  ack_deadline_seconds = 30
}
