terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_storage_bucket" "artifacts" {
  name          = "${var.project_id}-${var.environment}-aicp-artifacts"
  project       = var.project_id
  location      = var.region
  force_destroy = var.environment != "prod"

  versioning { enabled = true }

  encryption {
    default_kms_key_name = var.kms_key_id
  }

  lifecycle_rule {
    condition { age = 90 }
    action    { type = "Delete" }
  }

  uniform_bucket_level_access = true
  labels                      = var.labels
}

resource "google_storage_bucket" "models" {
  name          = "${var.project_id}-${var.environment}-aicp-models"
  project       = var.project_id
  location      = var.region
  force_destroy = false

  versioning { enabled = true }

  encryption {
    default_kms_key_name = var.kms_key_id
  }

  uniform_bucket_level_access = true
  labels                      = var.labels
}

resource "google_storage_bucket" "audit_logs" {
  name          = "${var.project_id}-${var.environment}-aicp-audit-logs"
  project       = var.project_id
  location      = var.region
  force_destroy = false

  versioning { enabled = true }

  retention_policy {
    is_locked        = var.environment == "prod"
    retention_period = 31536000  # 1 year
  }

  uniform_bucket_level_access = true
  labels                      = var.labels
}
