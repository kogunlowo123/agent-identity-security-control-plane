terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# GKE node service account
resource "google_service_account" "gke_node" {
  account_id   = "aicp-gke-node"
  display_name = "AICP GKE Node SA"
  project      = var.project_id
}

resource "google_project_iam_member" "gke_node_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_node.email}"
}

resource "google_project_iam_member" "gke_node_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_node.email}"
}

resource "google_project_iam_member" "gke_node_registry_reader" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.gke_node.email}"
}

# API service account
resource "google_service_account" "api" {
  account_id   = "aicp-api"
  display_name = "AICP API Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Workload Identity binding for API
resource "google_service_account_iam_member" "api_workload_identity" {
  service_account_id = google_service_account.api.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[aicp/api]"
}

# Agent runtime service account
resource "google_service_account" "agent_runtime" {
  account_id   = "aicp-agent-runtime"
  display_name = "AICP Agent Runtime Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "agent_runtime_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_runtime.email}"
}

resource "google_service_account_iam_member" "agent_runtime_workload_identity" {
  service_account_id = google_service_account.agent_runtime.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[aicp/agent-runtime]"
}

# RAG core service account
resource "google_service_account" "rag_core" {
  account_id   = "aicp-rag-core"
  display_name = "AICP RAG Core Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "rag_core_storage_reader" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.rag_core.email}"
}

resource "google_project_iam_member" "rag_core_vertex_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.rag_core.email}"
}

resource "google_service_account_iam_member" "rag_core_workload_identity" {
  service_account_id = google_service_account.rag_core.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[aicp/rag-core]"
}
