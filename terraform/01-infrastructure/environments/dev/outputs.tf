# =============================================================================
# Outputs for Dev Environment
# =============================================================================

# Networking
output "vpc_name" {
  description = "VPC name"
  value       = module.networking.vpc_name
}

output "subnet_name" {
  description = "Subnet name"
  value       = module.networking.subnet_name
}

# GKE
output "cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "cluster_location" {
  description = "GKE cluster location"
  value       = module.gke.cluster_location
}

# Command to connect to the cluster
output "gke_connect_command" {
  description = "Command to configure kubectl"
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --zone ${module.gke.cluster_location} --project ${var.project_id}"
}

# Shared resources (from 01-shared state)
output "docker_repository_url" {
  description = "URL for Docker images (from shared state)"
  value       = data.terraform_remote_state.shared.outputs.docker_repository_url
}

output "jenkins_service_account_email" {
  description = "Jenkins CI service account email (from shared state)"
  value       = data.terraform_remote_state.shared.outputs.jenkins_service_account_email
}
