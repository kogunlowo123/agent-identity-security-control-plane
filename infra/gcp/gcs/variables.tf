variable "project_id"   { type = string }
variable "region"       { type = string; default = "us-central1" }
variable "environment"  { type = string }
variable "kms_key_id"   { type = string; default = "" }
variable "labels"       { type = map(string); default = {} }
