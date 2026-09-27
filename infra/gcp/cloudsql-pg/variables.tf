variable "project_id" { type = string }
variable "region"     { type = string; default = "us-central1" }
variable "instance_name" { type = string }
variable "database_tier" { type = string; default = "db-g1-small" }
variable "ha_enabled"    { type = bool; default = false }
variable "disk_size_gb"  { type = number; default = 20 }
variable "vpc_network_id" { type = string }
variable "kms_key_id"    { type = string; default = "" }
variable "db_password"   { type = string; sensitive = true; default = "changeme" }
variable "deletion_protection" { type = bool; default = true }
variable "labels" { type = map(string); default = {} }
