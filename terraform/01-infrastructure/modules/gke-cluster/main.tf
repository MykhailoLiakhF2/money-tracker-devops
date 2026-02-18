# =============================================================================
# GKE Cluster Module
# =============================================================================

# -----------------------------------------------------------------------------
# GKE Cluster
# -----------------------------------------------------------------------------
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  project  = var.project_id
  location = var.zone  # Zonal cluster (cheaper) - single zone

  # Remove default node pool, we create our own separately
  # This is best practice - gives more control
  remove_default_node_pool = true
  initial_node_count       = 1

  # Network - connect to our VPC
  network    = var.vpc_name
  subnetwork = var.subnet_name

  # VPC-native cluster - uses secondary ranges for pods/services
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name      # "pods"
    services_secondary_range_name = var.services_range_name  # "services"
  }

  # Private cluster - nodes without public IPs
  private_cluster_config {
    enable_private_nodes    = true   # Nodes without public IPs
    enable_private_endpoint = false  # API accessible from internet (for kubectl)
    master_ipv4_cidr_block  = "172.16.0.0/28"  # CIDR for control plane
  }

  # Who can access the Kubernetes API
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = var.master_authorized_cidr
      display_name = "admin-access"
    }
  }

  # Release channel - automatic updates from Google
  release_channel {
    channel = var.release_channel  # REGULAR - stable
  }

  # Workload Identity - secure pod access to GCP APIs
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Logging and monitoring
  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  # Addons
  addons_config {
    # Horizontal Pod Autoscaler - pod autoscaling
    horizontal_pod_autoscaling {
      disabled = false
    }
    # HTTP Load Balancing - for Ingress
    http_load_balancing {
      disabled = false
    }
    # GCE Persistent Disk CSI Driver - for volumes
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
  }

  # Cluster autoscaling profile
  # OPTIMIZE_UTILIZATION = more aggressive scale-down (removes underutilized nodes faster)
  # vs BALANCED (default) which is more conservative
  cluster_autoscaling {
    autoscaling_profile = "OPTIMIZE_UTILIZATION"
  }

  # Prevent accidental deletion (true for prod, false for dev)
  deletion_protection = var.deletion_protection
}

# -----------------------------------------------------------------------------
# Node Pool - Worker Nodes
# -----------------------------------------------------------------------------
resource "google_container_node_pool" "primary_nodes" {
  name     = "${var.cluster_name}-node-pool"
  project  = var.project_id
  location = var.zone
  cluster  = google_container_cluster.primary.name

  # Autoscaling - automatically scales the number of nodes
  autoscaling {
    min_node_count = var.min_node_count  # Minimum 1
    max_node_count = var.max_node_count  # Maximum 3
  }

  # Initial number of nodes
  initial_node_count = var.min_node_count

  # Node configuration
  node_config {
    machine_type = var.machine_type  # e2-medium (2 vCPU, 4GB)
    disk_size_gb = var.disk_size_gb  # 50GB
    disk_type    = "pd-standard"     # Standard disk (cheaper)

    # Spot VM - 60-90% cheaper!
    # Can be preempted by Google with 30 sec warning
    # Ideal for dev/staging, use with caution in prod
    spot = var.spot_instances

    # OAuth scopes - what the node can do in GCP
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    # Workload Identity at node level
    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    # Node labels
    labels = {
      env = var.environment
    }

    # Tags for firewall rules
    tags = ["gke-node", var.cluster_name]
  }

  # Node upgrade strategy
  management {
    auto_repair  = true  # Automatically repair broken nodes
    auto_upgrade = true  # Automatically upgrade version
  }

  # Update one node at a time
  upgrade_settings {
    max_surge       = 1  # Add 1 new node
    max_unavailable = 0  # Don't shut down existing until new is ready
  }
}
