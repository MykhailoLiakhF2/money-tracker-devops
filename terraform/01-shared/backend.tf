# =============================================================================
# Backend Configuration - Remote State in GCS
# =============================================================================
# Shared resources have their own state, separate from per-environment infra.
# This state is referenced by environments via terraform_remote_state.
# =============================================================================

terraform {
  backend "gcs" {
    bucket = "your-terraform-state-bucket"  # Bucket from 00-bootstrap
    prefix = "money-tracker/shared"               # Shared resources state
  }
}
