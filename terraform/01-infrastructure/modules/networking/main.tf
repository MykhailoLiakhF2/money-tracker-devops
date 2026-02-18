# =============================================================================
# Networking Module: VPC, Subnets, NAT for GKE
# =============================================================================

# -----------------------------------------------------------------------------
# VPC - Virtual Private Cloud
# -----------------------------------------------------------------------------
# Isolated network for all resources. We don't use the default VPC -
# this is a production best practice for security and control.
# -----------------------------------------------------------------------------
resource "google_compute_network" "vpc" {
  name                    = "${var.cluster_name}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false  # We create subnets manually, not automatically
  routing_mode            = "REGIONAL"  # Routes only within the region
}

# -----------------------------------------------------------------------------
# Subnet - GKE Subnetwork
# -----------------------------------------------------------------------------
# Primary range for Nodes + two secondary ranges for Pods and Services.
# This is called a VPC-native cluster - better performance and security.
# -----------------------------------------------------------------------------
resource "google_compute_subnetwork" "gke_subnet" {
  name          = "${var.cluster_name}-subnet"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = var.subnet_cidr  # Primary range for Nodes (10.0.0.0/24)

  # Secondary ranges - required for VPC-native GKE
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr  # For Pods (10.1.0.0/20)
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr  # For Services (10.2.0.0/24)
  }

  # Enable Private Google Access - nodes without public IPs
  # can still reach Google APIs (Container Registry, etc.)
  private_ip_google_access = true
}

# -----------------------------------------------------------------------------
# Cloud Router - required for Cloud NAT
# -----------------------------------------------------------------------------
# Router manages routes in the region. Does nothing on its own,
# but is a mandatory component for NAT.
# -----------------------------------------------------------------------------
resource "google_compute_router" "router" {
  name    = "${var.cluster_name}-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.vpc.id
}

# -----------------------------------------------------------------------------
# Cloud NAT - Network Address Translation
# -----------------------------------------------------------------------------
# Private nodes have no public IPs (security!), but they need
# internet access for:
# - Pulling Docker images from Docker Hub, GCR
# - System updates
# - Access to external APIs
#
# NAT provides outbound traffic without inbound - nodes can see
# the internet, but the internet can't see nodes.
# -----------------------------------------------------------------------------
resource "google_compute_router_nat" "nat" {
  name                               = "${var.cluster_name}-nat"
  project                            = var.project_id
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"  # GCP automatically allocates IP
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  # Logging (optional, for debugging)
  log_config {
    enable = true
    filter = "ERRORS_ONLY"  # Errors only, to avoid paying for logs
  }
}

# -----------------------------------------------------------------------------
# Firewall Rules
# -----------------------------------------------------------------------------
# Base rules. GKE will add its own automatically, but we add
# explicit rules for better control.
# -----------------------------------------------------------------------------

# Allow internal traffic within VPC
resource "google_compute_firewall" "internal" {
  name    = "${var.cluster_name}-allow-internal"
  project = var.project_id
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"  # Ping for diagnostics
  }

  # Allowed from all internal ranges
  source_ranges = [
    var.subnet_cidr,    # Nodes
    var.pods_cidr,      # Pods
    var.services_cidr   # Services
  ]
}
