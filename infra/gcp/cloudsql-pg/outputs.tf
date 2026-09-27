output "connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.postgres.connection_name
}

output "private_ip" {
  description = "Private IP address"
  value       = google_sql_database_instance.postgres.private_ip_address
}

output "database_url" {
  description = "PostgreSQL connection URL (without password)"
  value       = "postgresql://aicp_user@${google_sql_database_instance.postgres.private_ip_address}/aicp_db"
  sensitive   = true
}
