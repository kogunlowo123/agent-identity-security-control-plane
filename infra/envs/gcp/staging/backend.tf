terraform {
  backend "gcs" {
    bucket = "aicp-staging-tfstate"
    prefix = "terraform/staging"
  }
}
