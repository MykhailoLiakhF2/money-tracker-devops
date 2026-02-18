# =============================================================================
# Variables for Prod Environment
# =============================================================================

variable "credentials_file" {
  description = "Path to GCP service account key JSON file"
  type        = string
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "zone" {
  description = "GCP zone"
  type        = string
}

variable "cluster_name" {
  description = "Name prefix for all resources"
  type        = string
}

# Network
variable "subnet_cidr" {
  description = "CIDR for nodes subnet"
  type        = string
  default     = "10.10.0.0/24"
}

variable "pods_cidr" {
  description = "CIDR for pods"
  type        = string
  default     = "10.11.0.0/20"
}

variable "services_cidr" {
  description = "CIDR for services"
  type        = string
  default     = "10.12.0.0/24"
}

# GKE
variable "machine_type" {
  description = "Machine type for GKE nodes"
  type        = string
  default     = "e2-medium"
}

variable "disk_size_gb" {
  description = "Disk size for nodes"
  type        = number
  default     = 50
}

variable "min_node_count" {
  description = "Minimum nodes in cluster"
  type        = number
  default     = 2
}

variable "max_node_count" {
  description = "Maximum nodes in cluster"
  type        = number
  default     = 6
}

variable "spot_instances" {
  description = "Use spot instances"
  type        = bool
  default     = false
}

variable "release_channel" {
  description = "GKE release channel"
  type        = string
  default     = "STABLE"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "deletion_protection" {
  description = "Prevent accidental cluster deletion"
  type        = bool
  default     = true
}

variable "master_authorized_cidr" {
  description = "CIDR block allowed to access the Kubernetes API"
  type        = string
}
