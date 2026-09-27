terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_kms_key_ring" "aicp" {
  name     = var.key_ring_name
  location = var.location
  project  = var.project_id
}

resource "google_kms_crypto_key" "etcd_secrets" {
  name            = "etcd-secrets"
  key_ring        = google_kms_key_ring.aicp.id
  rotation_period = "7776000s"  # 90 days

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "database" {
  name            = "database"
  key_ring        = google_kms_key_ring.aicp.id
  rotation_period = "7776000s"  # 90 days

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  labels = var.labels

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_kms_crypto_key" "application" {
  name            = "application-secrets"
  key_ring        = google_kms_key_ring.aicp.id
  rotation_period = "7776000s"  # 90 days

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  labels = var.labels
}

resource "google_kms_crypto_key" "signing" {
  name     = "jwt-signing"
  key_ring = google_kms_key_ring.aicp.id

  version_template {
    algorithm        = "RSA_SIGN_PKCS1_2048_SHA256"
    protection_level = "SOFTWARE"
  }

  labels = var.labels
}
