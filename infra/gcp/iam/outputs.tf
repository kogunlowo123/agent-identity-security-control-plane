output "gke_node_sa_email" {
  description = "GKE node service account email"
  value       = google_service_account.gke_node.email
}

output "api_sa_email" {
  description = "API service account email"
  value       = google_service_account.api.email
}

output "agent_runtime_sa_email" {
  description = "Agent runtime service account email"
  value       = google_service_account.agent_runtime.email
}

output "rag_core_sa_email" {
  description = "RAG core service account email"
  value       = google_service_account.rag_core.email
}
