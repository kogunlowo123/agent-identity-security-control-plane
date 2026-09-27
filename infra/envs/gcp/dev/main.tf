provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id"            { type = string }
variable "region"                { type = string; default = "us-central1" }
variable "environment"           { type = string }
variable "cluster_name"          { type = string }
variable "workload_min_nodes"    { type = number; default = 1 }
variable "workload_max_nodes"    { type = number; default = 3 }
variable "workload_machine_type" { type = string; default = "e2-standard-2" }
variable "db_instance_name"      { type = string }
variable "db_tier"               { type = string; default = "db-g1-small" }
variable "db_ha_enabled"         { type = bool; default = false }
variable "key_ring_name"         { type = string }
variable "labels"                { type = map(string); default = {} }

# ── KMS ───────────────────────────────────────────────────────────────────

module "kms" {
  source        = "../../../gcp/kms"
  project_id    = var.project_id
  location      = var.region
  key_ring_name = var.key_ring_name
  labels        = var.labels
}

# ── Network ───────────────────────────────────────────────────────────────

module "network" {
  source      = "../../../gcp/network"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  labels      = var.labels
}

# ── GKE ───────────────────────────────────────────────────────────────────

module "gke" {
  source       = "../../../gcp/gke"
  project_id   = var.project_id
  region       = var.region
  cluster_name = var.cluster_name
  labels       = var.labels

  vpc_name                      = module.network.vpc_name
  subnetwork_name               = module.network.subnetwork_name
  pods_secondary_range_name     = module.network.pods_secondary_range_name
  services_secondary_range_name = module.network.services_secondary_range_name
  kms_key_id                    = module.kms.etcd_secrets_key_id
  node_service_account          = module.iam.gke_node_sa_email

  workload_min_nodes    = var.workload_min_nodes
  workload_max_nodes    = var.workload_max_nodes
  workload_machine_type = var.workload_machine_type

  authorized_networks = [
    {
      cidr_block   = "10.0.0.0/8"
      display_name = "Internal"
    }
  ]
}

# ── Cloud SQL ─────────────────────────────────────────────────────────────

module "cloudsql" {
  source          = "../../../gcp/cloudsql-pg"
  project_id      = var.project_id
  region          = var.region
  instance_name   = var.db_instance_name
  database_tier   = var.db_tier
  ha_enabled      = var.db_ha_enabled
  vpc_network_id  = module.network.vpc_id
  kms_key_id      = module.kms.database_key_id
  labels          = var.labels
}

# ── IAM ───────────────────────────────────────────────────────────────────

module "iam" {
  source     = "../../../gcp/iam"
  project_id = var.project_id
  labels     = var.labels
}

# ── GCS ───────────────────────────────────────────────────────────────────

module "gcs" {
  source      = "../../../gcp/gcs"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
  kms_key_id  = module.kms.application_key_id
  labels      = var.labels
}

# ── Pub/Sub ───────────────────────────────────────────────────────────────

module "pubsub" {
  source     = "../../../gcp/pubsub"
  project_id = var.project_id
  labels     = var.labels
}
