terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_sql_database_instance" "postgres" {
  name             = var.instance_name
  database_version = "POSTGRES_16"
  project          = var.project_id
  region           = var.region

  deletion_protection = var.deletion_protection

  settings {
    tier              = var.database_tier
    availability_type = var.ha_enabled ? "REGIONAL" : "ZONAL"
    disk_size         = var.disk_size_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = var.vpc_network_id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "02:00"
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7   # Sunday
      hour         = 3
      update_track = "stable"
    }

    encryption_key_name = var.kms_key_id

    user_labels = var.labels
  }

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_sql_database" "aicp_db" {
  name     = "aicp_db"
  instance = google_sql_database_instance.postgres.name
  project  = var.project_id
}

resource "google_sql_user" "aicp_user" {
  name     = "aicp_user"
  instance = google_sql_database_instance.postgres.name
  project  = var.project_id
  password = var.db_password
}
