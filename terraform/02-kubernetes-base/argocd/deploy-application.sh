#!/bin/bash
# Deploy ArgoCD Application for money-tracker-dev

set -e

echo "Deploying ArgoCD Application: money-tracker-dev"

# Check if repository secret exists (only needed for private repos)
echo "Checking repository connection..."
if kubectl get secret github-money-tracker-repo -n argocd &>/dev/null; then
    echo "Repository secret exists"
else
    echo "WARNING: Repository secret not found."
    echo "If repo is PUBLIC — this is fine, ArgoCD can access it without credentials."
    echo "If repo is PRIVATE — create the secret first:"
    echo "  1. cp repository-secret.yaml.template repository-secret.yaml"
    echo "  2. Fill in GitHub PAT credentials"
    echo "  3. kubectl apply -f repository-secret.yaml"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Apply ArgoCD Application
echo "Applying ArgoCD Application manifest..."
kubectl apply -f applications/money-tracker-dev.yaml

sleep 3

echo "Checking application status..."
kubectl get application money-tracker-dev -n argocd

echo ""
echo "Next steps:"
echo "  1. Open ArgoCD UI"
echo "  2. Check application 'money-tracker-dev'"
echo "  3. Click 'Sync' to deploy from Git"
