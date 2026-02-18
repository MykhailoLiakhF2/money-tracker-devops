# =============================================================================
# Dev Environment - Main Configuration
# =============================================================================
# This environment creates ONLY per-cluster resources (VPC, GKE).
# Shared resources (Jenkins SA, Artifact Registry) live in 01-shared/
# and are read via terraform_remote_state.
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
# Remote State - Read shared resources
# -----------------------------------------------------------------------------
# Shared resources (Jenkins SA, Artifact Registry) are managed in 01-shared/.
# We read their outputs here to set up per-cluster IAM bindings.
# -----------------------------------------------------------------------------
data "terraform_remote_state" "shared" {
  backend = "gcs"
  config = {
    bucket = "${var.project_id}-terraform-state"
    prefix = "money-tracker/shared"
  }
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------
data "google_project" "current" {
  project_id = var.project_id
}

# -----------------------------------------------------------------------------
# Networking Module
# -----------------------------------------------------------------------------
module "networking" {
  source = "../../modules/networking"

  project_id    = var.project_id
  region        = var.region
  cluster_name  = var.cluster_name
  subnet_cidr   = var.subnet_cidr
  pods_cidr     = var.pods_cidr
  services_cidr = var.services_cidr
}

# -----------------------------------------------------------------------------
# GKE Cluster Module
# -----------------------------------------------------------------------------
module "gke" {
  source = "../../modules/gke-cluster"

  project_id          = var.project_id
  cluster_name        = var.cluster_name
  zone                = var.zone
  vpc_name            = module.networking.vpc_name
  subnet_name         = module.networking.subnet_name
  pods_range_name     = module.networking.pods_range_name
  services_range_name = module.networking.services_range_name
  machine_type        = var.machine_type
  disk_size_gb        = var.disk_size_gb
  min_node_count      = var.min_node_count
  max_node_count      = var.max_node_count
  spot_instances      = var.spot_instances
  release_channel     = var.release_channel
  environment         = var.environment
  deletion_protection = var.deletion_protection
  master_authorized_cidr = var.master_authorized_cidr

  depends_on = [module.networking]
}

# -----------------------------------------------------------------------------
# IAM: GKE nodes → Artifact Registry (pull access)
# -----------------------------------------------------------------------------
# Each cluster needs its own binding — node SA is per-cluster.
# Registry name comes from shared state.
# -----------------------------------------------------------------------------
resource "google_artifact_registry_repository_iam_member" "gke_reader" {
  project    = var.project_id
  location   = var.region
  repository = data.terraform_remote_state.shared.outputs.artifact_registry_repository_name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${data.google_project.current.number}-compute@developer.gserviceaccount.com"
}
