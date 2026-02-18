# =============================================================================
# Variables for Bootstrap
# =============================================================================

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the state bucket"
  type        = string
  default     = "europe-central2"
}

variable "credentials_file" {
  description = "Path to GCP service account key JSON file"
  type        = string
}
