# ArgoCD — GitOps Continuous Delivery

## Overview
ArgoCD monitors the GitHub repository and syncs Kubernetes manifests to the cluster.
Jenkins handles CI (build + push), ArgoCD handles CD (deploy).

## Directory Structure
```
argocd/
├── values.yaml                         # Helm chart values
├── repository-secret.yaml.template     # Template for GitHub credentials
├── deploy-application.sh               # Helper script
└── applications/
    └── money-tracker-dev.yaml          # ArgoCD Application manifest
```

## Quick Start

### 1. Install ArgoCD
```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm install argocd argo/argo-cd \
  --namespace argocd --create-namespace \
  --values values.yaml
```

### 2. Get Admin Password
```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

### 3. Connect GitHub Repository
If repo is **public** — no credentials needed.
If repo is **private**:
```bash
cp repository-secret.yaml.template repository-secret.yaml
# Edit and fill in GitHub PAT
kubectl apply -f repository-secret.yaml
```

### 4. Deploy Application
```bash
kubectl apply -f applications/money-tracker-dev.yaml
# Or use: ./deploy-application.sh
```

### 5. Sync
```bash
# Via ArgoCD UI: Applications → money-tracker-dev → Sync
# Via CLI:
argocd app sync money-tracker-dev
```

## Workflow
```
Code Push → Jenkins CI (test/build/push) → Update image tag in Git →
ArgoCD detects OutOfSync → Manual Sync → Deploy to GKE
```
