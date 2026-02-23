#!/usr/bin/env bash
set -euo pipefail
REL=${REL:-ester}
NS=${NS:-ester}
IMG=${IMG:-ghcr.io/OWNER/REPO}
TAG=${TAG:-latest}
helm upgrade --install "$REL" charts/ester -n "$NS" --create-namespace   --set image.repository="$IMG" --set image.tag="$TAG"   --set env.JWT_SECRET="${JWT_SECRET:-change_me}"   --set env.ENCRYPTION_MASTER_KEY_BASE64="${ENCRYPTION_MASTER_KEY_BASE64:-}"   --set serviceMonitor.enabled=true --set prometheusRule.enabled=true
