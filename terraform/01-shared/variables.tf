# =============================================================================
# Variables for Shared Resources
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
  description = "GCP region for Artifact Registry"
  type        = string
}
