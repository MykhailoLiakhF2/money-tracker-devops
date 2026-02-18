# =============================================================================
# Outputs for Shared Resources
# =============================================================================
# These outputs are consumed by environments via terraform_remote_state.
# =============================================================================

output "jenkins_service_account_email" {
  description = "Jenkins CI service account email"
  value       = google_service_account.jenkins.email
}

output "artifact_registry_repository_name" {
  description = "Artifact Registry repository name (for IAM bindings in environments)"
  value       = google_artifact_registry_repository.docker_repo.name
}

output "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID"
  value       = google_artifact_registry_repository.docker_repo.repository_id
}

output "docker_repository_url" {
  description = "Full URL for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

output "docker_tag_example" {
  description = "Example Docker tag command"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/IMAGE_NAME:TAG"
}

output "jenkins_setup_instructions" {
  description = "How to create Jenkins SA key manually"
  value       = <<-EOT

    Shared resources created!

    Jenkins SA: ${google_service_account.jenkins.email}
    Registry:   ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}

    To create a key for Jenkins (do NOT use Terraform for this):
      gcloud iam service-accounts keys create jenkins-sa-key.json \
        --iam-account=${google_service_account.jenkins.email}

    Store it as a Kubernetes secret:
      kubectl create secret generic jenkins-gcp-sa \
        --from-file=key.json=jenkins-sa-key.json \
        -n jenkins

    Then DELETE the local key file.
    Phase 4: migrate to Workload Identity (no keys at all).
  EOT
}
