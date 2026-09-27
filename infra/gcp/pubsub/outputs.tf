output "topic_ids" {
  description = "Map of topic name to topic ID"
  value       = { for k, v in google_pubsub_topic.topics : k => v.id }
}

output "subscription_ids" {
  description = "Map of subscription name to subscription ID"
  value       = { for k, v in google_pubsub_subscription.subscriptions : k => v.id }
}
