terraform {
  backend "gcs" {
    bucket = "aicp-tfstate-dev"
    prefix = "terraform/state"
  }

  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}
