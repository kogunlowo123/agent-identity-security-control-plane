output "artifacts_bucket_name" { value = google_storage_bucket.artifacts.name }
output "models_bucket_name"    { value = google_storage_bucket.models.name }
output "audit_logs_bucket_name" { value = google_storage_bucket.audit_logs.name }
