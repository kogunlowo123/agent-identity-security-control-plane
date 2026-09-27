variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region for the cluster"
  default     = "us-central1"
}

variable "cluster_name" {
  type        = string
  description = "Name of the GKE cluster"
  default     = "aicp-cluster"
}

variable "vpc_name" {
  type        = string
  description = "VPC network name"
}

variable "subnetwork_name" {
  type        = string
  description = "Subnetwork name"
}

variable "pods_secondary_range_name" {
  type        = string
  description = "Secondary IP range name for pods"
}

variable "services_secondary_range_name" {
  type        = string
  description = "Secondary IP range name for services"
}

variable "master_ipv4_cidr" {
  type        = string
  description = "CIDR block for GKE master"
  default     = "172.16.0.32/28"
}

variable "authorized_networks" {
  type = list(object({
    cidr_block   = string
    display_name = string
  }))
  description = "Authorized networks for master access"
  default     = []
}

variable "kms_key_id" {
  type        = string
  description = "KMS key ID for etcd encryption"
}

variable "node_service_account" {
  type        = string
  description = "Service account email for GKE nodes"
}

variable "system_node_count" {
  type        = number
  description = "Number of system nodes"
  default     = 1
}

variable "system_machine_type" {
  type        = string
  description = "Machine type for system node pool"
  default     = "e2-medium"
}

variable "workload_min_nodes" {
  type        = number
  description = "Minimum workload nodes"
  default     = 1
}

variable "workload_max_nodes" {
  type        = number
  description = "Maximum workload nodes"
  default     = 5
}

variable "workload_machine_type" {
  type        = string
  description = "Machine type for workload node pool"
  default     = "e2-standard-4"
}

variable "release_channel" {
  type        = string
  description = "GKE release channel"
  default     = "REGULAR"
}

variable "labels" {
  type        = map(string)
  description = "Labels to apply to all resources"
  default     = {}
}
