# =============================================================================
# Bootstrap: Create GCS bucket for Terraform remote state
# =============================================================================
# This is a one-time setup. Run this first, then use remote backend everywhere.
# State for this module is stored LOCALLY (chicken-and-egg problem).
# =============================================================================

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # LOCAL backend - no remote state for bootstrap
  # This is intentional!
}

provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
  region      = var.region
}

# -----------------------------------------------------------------------------
# GCS Bucket for Terraform State
# -----------------------------------------------------------------------------
resource "google_storage_bucket" "terraform_state" {
  name     = "${var.project_id}-terraform-state"
  location = var.region
  project  = var.project_id

  # Prevent accidental deletion
  force_destroy = false

  # Enable versioning - keeps history of state files
  versioning {
    enabled = true
  }

  # Lifecycle rule - delete old versions after 30 days
  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  # Uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  # Labels for organization
  labels = {
    environment = "shared"
    purpose     = "terraform-state"
    managed_by  = "terraform"
  }
}

# -----------------------------------------------------------------------------
# Output - bucket name for use in other modules
# -----------------------------------------------------------------------------
output "state_bucket_name" {
  description = "GCS bucket name for Terraform state"
  value       = google_storage_bucket.terraform_state.name
}

output "state_bucket_url" {
  description = "GCS bucket URL"
  value       = google_storage_bucket.terraform_state.url
}
