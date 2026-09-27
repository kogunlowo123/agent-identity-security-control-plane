output "key_ring_id" {
  description = "KMS key ring ID"
  value       = google_kms_key_ring.aicp.id
}

output "etcd_secrets_key_id" {
  description = "KMS key ID for etcd secrets encryption"
  value       = google_kms_crypto_key.etcd_secrets.id
}

output "database_key_id" {
  description = "KMS key ID for database encryption"
  value       = google_kms_crypto_key.database.id
}

output "application_key_id" {
  description = "KMS key ID for application secrets"
  value       = google_kms_crypto_key.application.id
}

output "signing_key_id" {
  description = "KMS key ID for JWT signing"
  value       = google_kms_crypto_key.signing.id
}
