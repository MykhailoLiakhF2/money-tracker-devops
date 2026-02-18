# 🏗️ Terraform Infrastructure Architecture

This directory contains the Infrastructure as Code (IaC) definitions for the Money Tracker project. The infrastructure is designed using a **layered approach** to ensure security, modularity, and ease of maintenance.

---

## 층 (Layers) Overview

The deployment is split into four distinct phases to handle cross-dependencies and security boundaries effectively.

### 0. [Bootstrap](./00-bootstrap)
**Purpose**: Solves the "chicken and egg" problem by creating the initial GCS bucket for remote state.
- Stores its own state **locally**.
- Once run, all other modules use the created bucket for remote state.

### 1. [Shared Resources](./01-shared)
**Purpose**: Global project assets shared across all environments.
- **Artifact Registry**: Docker repository used by both Dev and Prod clusters.
- **Service Accounts**: Jenkins CI identity with dedicated IAM roles.
- **Workload Identity**: Foundation for secure GKE-to-GCP authentication.

### 2. [Infrastructure](./01-infrastructure)
**Purpose**: Per-environment core networking and compute.
- **VPC & Subnets**: Custom networking with secondary ranges for Pods and Services.
- **GKE Cluster**: Private clusters with Master Authorized Networks enabled.
- **Cloud NAT**: Allows private GKE nodes to access the internet securely.

### 3. [Kubernetes Base](./02-kubernetes-base)
**Purpose**: Cluster-level services required before application deployment.
- **ArgoCD**: GitOps operator for continuous delivery.
- **Cert-Manager**: Automated SSL/TLS certificate management via Let's Encrypt.
- **Ingress-Nginx**: Layer-7 load balancing and routing.

---

## 🔐 State Management

The project uses **Google Cloud Storage (GCS)** as a remote backend. To ensure flexibility across different project IDs, the backend is configured using dynamic flags during initialization.

### Initialization Pattern
Instead of hardcoding the bucket name in every `backend.tf`, we use the following pattern:

```hcl
# backend.tf
terraform {
  backend "gcs" {
    # bucket name is provided via -backend-config during init
    prefix = "money-tracker/prod" 
  }
}
```

**Execution Command**:
```bash
terraform init -backend-config="bucket=${PROJECT_ID}-terraform-state"
```

---

## 🛡️ Security Hardening

- **Private Nodes**: All GKE nodes are private (no public IPs).
- **Master Authorized Networks**: Access to the Kubernetes API is restricted to specific CIDRs (defined via `master_authorized_cidr`).
- **Least Privilege**: Service accounts are granted only the minimum required IAM roles (e.g., `artifactregistry.reader` for nodes).
- **Versioning**: GCS state bucket has versioning enabled to prevent data loss or accidental corruption.

---

## 🛠️ Maintenance

### Adding a New Environment
1.  Copy `terraform/01-infrastructure/environments/dev` to a new folder (e.g., `staging`).
2.  Update the `prefix` in `backend.tf`.
3.  Adjust `terraform.tfvars` with unique CIDR ranges and environment-specific settings.

---
*For step-by-step deployment instructions, refer to the [SETUP_GUIDE.md](./SETUP_GUIDE.md).*
