output "vpc_id" {
  description = "VPC network ID"
  value       = google_compute_network.vpc.id
}

output "vpc_name" {
  description = "VPC network name"
  value       = google_compute_network.vpc.name
}

output "subnetwork_name" {
  description = "Primary subnetwork name"
  value       = google_compute_subnetwork.primary.name
}

output "subnetwork_id" {
  description = "Primary subnetwork ID"
  value       = google_compute_subnetwork.primary.id
}

output "pods_secondary_range_name" {
  description = "Secondary range name for pods"
  value       = "pods"
}

output "services_secondary_range_name" {
  description = "Secondary range name for services"
  value       = "services"
}

output "nat_ip" {
  description = "NAT gateway IP (auto-allocated)"
  value       = google_compute_router_nat.nat.name
}
