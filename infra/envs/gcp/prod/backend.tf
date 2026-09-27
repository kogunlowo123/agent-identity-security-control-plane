terraform {
  backend "gcs" {
    bucket = "aicp-prod-tfstate"
    prefix = "terraform/prod"
  }
}
