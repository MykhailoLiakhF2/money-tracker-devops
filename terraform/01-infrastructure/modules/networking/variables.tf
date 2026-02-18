# =============================================================================
# Variables for Networking Module
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "cluster_name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "subnet_cidr" {
  description = "CIDR range for the subnet (nodes)"
  type        = string
  default     = "10.0.0.0/24"
}

variable "pods_cidr" {
  description = "CIDR range for pods (secondary range)"
  type        = string
  default     = "10.1.0.0/20"
}

variable "services_cidr" {
  description = "CIDR range for services (secondary range)"
  type        = string
  default     = "10.2.0.0/24"
}
