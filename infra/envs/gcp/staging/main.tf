module "gke" {
  source = "../../../gcp/gke"

  project_id   = var.project_id
  region       = var.region
  cluster_name = "aicp-staging"
  environment  = "staging"

  node_count        = 2
  machine_type      = "n2-standard-4"
  min_node_count    = 1
  max_node_count    = 5
}

module "cloudsql" {
  source = "../../../gcp/cloudsql"

  project_id    = var.project_id
  region        = var.region
  instance_name = "aicp-staging-postgres"
  tier          = "db-custom-2-8192"
  environment   = "staging"
}
