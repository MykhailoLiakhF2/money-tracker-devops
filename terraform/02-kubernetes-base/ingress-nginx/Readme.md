# NGINX Ingress Controller

Ingress controller for managing incoming HTTP/HTTPS traffic to the GKE cluster.

## What It Does

- Creates a GCP External Load Balancer with a public IP
- Routes traffic to services based on hostname and path rules
- Works with cert-manager for automatic SSL certificates (next step)

## Prerequisites

- GKE cluster running and kubectl connected
- Helm 3 installed

## Installation Steps

### Step 1: Add Helm Repository

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
```

### Step 2: Create Namespace

```bash
kubectl create namespace ingress-nginx
```

### Step 3: Install with Custom Values

```bash
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --values values.yaml
```

### Step 4: Verify Installation

```bash
# Check pods are running
kubectl get pods -n ingress-nginx

# Check service and External IP (may take 1-2 minutes)
kubectl get svc -n ingress-nginx
```

## Verification

When ready, you should see:
- 2 controller pods in `Running` state
- 1 default-backend pod in `Running` state  
- Service with `EXTERNAL-IP` (not `<pending>`)

## Useful Commands

```bash
# View controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller

# Describe service (see Load Balancer details)
kubectl describe svc ingress-nginx-controller -n ingress-nginx
```

## Uninstall

```bash
helm uninstall ingress-nginx -n ingress-nginx
kubectl delete namespace ingress-nginx
```