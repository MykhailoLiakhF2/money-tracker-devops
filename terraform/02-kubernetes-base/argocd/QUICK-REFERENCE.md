# ArgoCD Quick Reference

## Check Status
```bash
kubectl get applications -n argocd
kubectl describe application money-tracker-dev -n argocd
kubectl get application money-tracker-dev -n argocd -w
```

## Sync
```bash
# CLI
argocd app sync money-tracker-dev

# kubectl
kubectl patch application money-tracker-dev -n argocd \
  --type merge \
  -p '{"operation":{"sync":{"revision":"HEAD"}}}'
```

## Troubleshooting
```bash
# Repo server logs (Git fetch issues)
kubectl logs -n argocd deployment/argocd-repo-server

# Application controller logs
kubectl logs -n argocd deployment/argocd-application-controller

# Check repo secret
kubectl get secrets -n argocd -l argocd.argoproj.io/secret-type=repository

# Application events
kubectl get events -n argocd | grep money-tracker-dev
```

## Delete Application
```bash
kubectl delete application money-tracker-dev -n argocd
```
