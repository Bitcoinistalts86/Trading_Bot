variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "location" {
  type    = string
  default = "US"
}

variable "artifact_registry" {
  type    = string
  default = "ai-trading-artifacts"
}

variable "pubsub_topics" {
  type    = list(string)
  default = ["market.binance.ethusdt", "market.uniswap.ethusdt", "features.ethusdt", "model.retrain.trigger"]
}

variable "dataflow_region" {
  type    = string
  default = "us-central1"
}
