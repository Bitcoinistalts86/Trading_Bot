output "project_id" {
  value = var.project_id
}

output "pubsub_topics" {
  value = [for t in google_pubsub_topic.topics : t.name]
}

output "bigquery_dataset" {
  value = google_bigquery_dataset.ingest.dataset_id
}

output "connectors_service_account" {
  value = google_service_account.connectors_sa.email
}
