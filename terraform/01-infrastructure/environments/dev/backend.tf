# =============================================================================
# Backend Configuration - Remote State in GCS
# =============================================================================

terraform {
  backend "gcs" {
    bucket = "your-terraform-state-bucket"  # Bucket from 00-bootstrap
    prefix = "money-tracker/infrastructure"       # New project, separate state
  }
}
