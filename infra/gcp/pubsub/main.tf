terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

locals {
  topics = ["identity-issued", "identity-revoked", "identity-violated"]
}

resource "google_pubsub_topic" "topics" {
  for_each = toset(local.topics)
  name     = each.value
  project  = var.project_id
  labels   = var.labels
}

resource "google_pubsub_topic" "dead_letter" {
  for_each = toset(local.topics)
  name     = "${each.value}-dlq"
  project  = var.project_id
  labels   = var.labels
}

resource "google_pubsub_subscription" "subscriptions" {
  for_each = toset(local.topics)
  name     = "${each.value}-sub"
  project  = var.project_id
  topic    = google_pubsub_topic.topics[each.key].id

  ack_deadline_seconds       = 30
  message_retention_duration = "604800s"  # 7 days

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter[each.key].id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = var.labels
}
