# =============================================================================
# Shared Resources - Created once, used by all environments
# =============================================================================
# Resources here are project-level (not per-cluster):
#   - Jenkins CI service account (no key — use Workload Identity or gcloud)
#   - Artifact Registry repository (shared image store)
#   - IAM binding: Jenkins → Artifact Registry writer
#
# Run this BEFORE any environment (dev/prod).
# Environments read these outputs via terraform_remote_state.
# =============================================================================

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  credentials = file(var.credentials_file)
  project     = var.project_id
  region      = var.region
}

# -----------------------------------------------------------------------------
# Jenkins CI Service Account
# -----------------------------------------------------------------------------
# Purpose: identity for Jenkins pipelines to push Docker images.
# No key is generated here — keys in Terraform state are a security risk.
# Use Workload Identity (Phase 4) or create key manually via gcloud.
# -----------------------------------------------------------------------------
resource "google_service_account" "jenkins" {
  account_id   = "jenkins-money-tracker"
  display_name = "Jenkins CI for Money Tracker"
  description  = "Service account for Jenkins CI pipelines - builds and pushes Docker images"
  project      = var.project_id
}

# -----------------------------------------------------------------------------
# Artifact Registry - Docker image repository
# -----------------------------------------------------------------------------
# Shared across all environments — one registry, images tagged per env.
# Example: REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REGISTRY/backend:prod-v1.0
# -----------------------------------------------------------------------------
resource "google_artifact_registry_repository" "docker_repo" {
  project       = var.project_id
  location      = var.region
  repository_id = "gke-images"
  description   = "Docker repository for Money Tracker project"
  format        = "DOCKER"

  # Cleanup policy - automatically delete old images
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-old-images"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s"   # 7 days
    }
  }

  cleanup_policies {
    id     = "keep-recent-tagged"
    action = "KEEP"
    condition {
      tag_state    = "TAGGED"
      tag_prefixes = ["v", "release", "prod", "dev"]
    }
  }

  labels = {
    managed_by = "terraform"
    project    = "money-tracker"
  }
}

# -----------------------------------------------------------------------------
# IAM: Jenkins → Artifact Registry (push access)
# -----------------------------------------------------------------------------
# Repository-level binding (not project-level) — least privilege.
# Jenkins can only push to this specific registry, not all registries in project.
# -----------------------------------------------------------------------------
resource "google_artifact_registry_repository_iam_member" "jenkins_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.jenkins.email}"
}
