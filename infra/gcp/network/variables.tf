variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
}

variable "subnet_cidr" {
  type        = string
  description = "Primary subnet CIDR"
  default     = "10.0.0.0/24"
}

variable "pods_cidr" {
  type        = string
  description = "Secondary range CIDR for pods"
  default     = "10.1.0.0/16"
}

variable "services_cidr" {
  type        = string
  description = "Secondary range CIDR for services"
  default     = "10.2.0.0/20"
}

variable "labels" {
  type        = map(string)
  description = "Labels to apply to resources"
  default     = {}
}
