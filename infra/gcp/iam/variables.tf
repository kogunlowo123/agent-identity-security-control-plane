variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "labels" {
  type        = map(string)
  description = "Labels"
  default     = {}
}
