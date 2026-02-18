# =============================================================================
# Variables for GKE Cluster Module
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "cluster_name" {
  description = "GKE cluster name"
  type        = string
}

variable "zone" {
  description = "GCP zone for zonal cluster"
  type        = string
}

variable "vpc_name" {
  description = "VPC network name"
  type        = string
}

variable "subnet_name" {
  description = "Subnet name"
  type        = string
}

variable "pods_range_name" {
  description = "Name of secondary range for pods"
  type        = string
}

variable "services_range_name" {
  description = "Name of secondary range for services"
  type        = string
}

variable "machine_type" {
  description = "Machine type for nodes"
  type        = string
  default     = "e2-medium"
}

variable "disk_size_gb" {
  description = "Disk size for nodes in GB"
  type        = number
  default     = 50
}

variable "min_node_count" {
  description = "Minimum number of nodes"
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "Maximum number of nodes"
  type        = number
  default     = 3
}

variable "spot_instances" {
  description = "Use spot instances (cheaper but can be preempted)"
  type        = bool
  default     = true
}

variable "release_channel" {
  description = "GKE release channel: RAPID, REGULAR, or STABLE"
  type        = string
  default     = "REGULAR"
}

variable "environment" {
  description = "Environment label (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "deletion_protection" {
  description = "Prevent accidental cluster deletion. Must be true for prod."
  type        = bool
  default     = true
}

variable "master_authorized_cidr" {
  description = "CIDR block allowed to access the Kubernetes API (e.g. your VPN IP)"
  type        = string
}
