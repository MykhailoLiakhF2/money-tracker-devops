# GCP Terraform Setup Guide

This guide describes how to deploy the infrastructure from scratch.

## 1. Bootstrap (One-time setup)
First, you must create the bucket where Terraform will store its state.

1. Go to `terraform/00-bootstrap`.
2. Update `terraform.tfvars` with your `project_id`.
3. Run:
   ```bash
   terraform init
   terraform apply
   ```
   *This will create a bucket named `<project_id>-terraform-state`.*

## 2. Infrastructure Deployment Checklist

### A. Shared Resources (`01-shared`)
1. Go to `terraform/01-shared`.
2. **Important**: Create `terraform.tfvars` (copy from `.example`) and set your `project_id`.
3. Since Terraform backends don't support variables, run init like this:
   ```bash
   terraform init -backend-config="bucket=<your-project-id>-terraform-state"
   ```
4. Run `terraform apply`.

### B. Environments (`dev` / `prod`)
1. Go to `terraform/01-infrastructure/environments/<env>`.
2. **Required Variables**: Ensure you set `master_authorized_cidr` in your `terraform.tfvars`.
   *   If you don't set this, Terraform will ask for it during `plan`.
   *   Example: `master_authorized_cidr = "0.0.0.0/0"` (Open access - **NOT recommended for prod**) or your specific IP: `master_authorized_cidr = "1.2.3.4/32"`.
3. Run init with the same backend config:
   ```bash
   terraform init -backend-config="bucket=<your-project-id>-terraform-state"
   ```
4. Run `terraform plan`.

## Troubleshooting: "Backend configuration changed"
If you see this error, it means you've switched branches or manually edited `backend.tf`. Terraform just needs to sync its local cache.
**Fix**:
```bash
terraform init -reconfigure
```
