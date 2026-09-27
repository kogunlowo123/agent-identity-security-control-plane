module "gke" {
  source = "../../../gcp/gke"

  project_id   = var.project_id
  region       = var.region
  cluster_name = "aicp-prod"
  environment  = "prod"

  node_count        = 3
  machine_type      = "n2-standard-8"
  min_node_count    = 3
  max_node_count    = 20
}

module "cloudsql" {
  source = "../../../gcp/cloudsql"

  project_id    = var.project_id
  region        = var.region
  instance_name = "aicp-prod-postgres"
  tier          = "db-custom-4-16384"
  environment   = "prod"

  high_availability = true
  deletion_protection = true
}
