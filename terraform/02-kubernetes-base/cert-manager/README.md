# Cert-Manager

Automatic SSL/TLS certificate management for Kubernetes using Let's Encrypt.

## What It Does

- Automatically obtains SSL certificates from Let's Encrypt
- Automatically renews certificates before expiry (30 days before)
- Integrates with Ingress resources via annotations

## How It Works

1. You create an Ingress with TLS configuration
2. Cert-manager sees the annotation and requests a certificate
3. Let's Encrypt validates you own the domain (HTTP-01 challenge via nginx)
4. Certificate is stored as a Kubernetes Secret
5. Ingress uses the Secret for HTTPS

## Prerequisites

- GKE cluster running
- ingress-nginx installed and working
- A domain name pointing to your Load Balancer IP

## Installation Steps

### Step 1: Add Helm Repository

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
```

### Step 2: Create Namespace

```bash
kubectl create namespace cert-manager
```

### Step 3: Install with Custom Values

```bash
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --values values.yaml
```

### Step 4: Verify Installation

```bash
# Check pods are running
kubectl get pods -n cert-manager

# Check CRDs are installed
kubectl get crds | grep cert-manager
```

### Step 5: Create ClusterIssuers

First, edit `cluster-issuers.yaml` and replace `your-email@example.com` with your real email.

```bash
kubectl apply -f cluster-issuers.yaml
```

### Step 6: Verify Issuers

```bash
kubectl get clusterissuers
```

Both should show `READY: True`.

## Using Certificates in Ingress

Add these annotations to your Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"  # or letsencrypt-staging for testing
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - myapp.example.com
    secretName: myapp-tls  # cert-manager will create this
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 80
```

## Staging vs Production

- **letsencrypt-staging**: Use for testing. Certificates are not trusted by browsers but have no rate limits.
- **letsencrypt-prod**: Use for real sites. Certificates are trusted but have rate limits (50 per week per domain).

Always test with staging first!

## Useful Commands

```bash
# View certificates
kubectl get certificates -A

# View certificate requests
kubectl get certificaterequests -A

# View cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager

# Describe a certificate for troubleshooting
kubectl describe certificate <name> -n <namespace>
```

## Uninstall

```bash
kubectl delete -f cluster-issuers.yaml
helm uninstall cert-manager -n cert-manager
kubectl delete namespace cert-manager
```
