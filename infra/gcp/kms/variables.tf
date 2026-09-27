variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "location" {
  type        = string
  description = "KMS key ring location (e.g. us-central1 or global)"
  default     = "us-central1"
}

variable "key_ring_name" {
  type        = string
  description = "KMS key ring name"
  default     = "aicp-keyring"
}

variable "labels" {
  type        = map(string)
  description = "Labels to apply to KMS resources"
  default     = {}
}
