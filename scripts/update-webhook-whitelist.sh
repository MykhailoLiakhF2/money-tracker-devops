#!/bin/bash
# =============================================================================
# update-webhook-whitelist.sh — Generate ingress whitelist with GitHub IPs
# =============================================================================
# Usage: ./scripts/update-webhook-whitelist.sh [--apply]
#
# Without --apply: prints the whitelist string (dry-run)
# With --apply:    updates values-prod.yaml and runs helm upgrade
#
# GitHub publishes webhook IPs at https://api.github.com/meta
# These can change — run this script periodically or when webhooks fail.
# =============================================================================

set -euo pipefail

PERSONAL_IP="<YOUR_IP>/32"  # Replace with your actual IP
VALUES_FILE="jenkins/helm-values/values-prod.yaml"
HELM_RELEASE="jenkins"
HELM_NAMESPACE="jenkins"

# --- Fetch current GitHub webhook IPs ---
echo "Fetching GitHub webhook IPs..."
GITHUB_IPS=$(curl -sf https://api.github.com/meta | python3 -c "import sys,json; print(','.join(json.load(sys.stdin)['hooks']))")

if [ -z "$GITHUB_IPS" ]; then
    echo "ERROR: Failed to fetch GitHub IPs" >&2
    exit 1
fi

WHITELIST="${PERSONAL_IP},${GITHUB_IPS}"
echo "Whitelist: ${WHITELIST}"

# --- Dry-run or apply ---
if [ "${1:-}" = "--apply" ]; then
    echo ""
    echo "Updating ${VALUES_FILE}..."

    # Replace the whitelist line in values file
    # Uses | as sed delimiter because IPs contain /
    sed -i "s|nginx.ingress.kubernetes.io/whitelist-source-range:.*|nginx.ingress.kubernetes.io/whitelist-source-range: \"${WHITELIST}\"|" "$VALUES_FILE"

    echo "Running helm upgrade..."
    helm upgrade "$HELM_RELEASE" jenkins/jenkins \
        -n "$HELM_NAMESPACE" \
        -f "$VALUES_FILE" \
        --wait

    echo ""
    echo "✅ Whitelist updated and deployed"
else
    echo ""
    echo "Dry-run. To apply, run:"
    echo "  ./scripts/update-webhook-whitelist.sh --apply"
fi
