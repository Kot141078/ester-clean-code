#!/usr/bin/env bash
set -euo pipefail

# Deploy v dva klastera odinakovogo reliza.
# Primer:
#   REL=ester NS=ester IMG=ghcr.io/OWNER/REPO TAG=main #   CTX1=k8s-primary CTX2=k8s-secondary ./mc_sync.sh

REL=${REL:-ester}
NS=${NS:-ester}
IMG=${IMG:-ghcr.io/OWNER/REPO}
TAG=${TAG:-latest}
CTX1=${CTX1:-k8s-primary}
CTX2=${CTX2:-k8s-secondary}

helm upgrade --install "$REL" charts/ester -n "$NS" --kube-context "$CTX1" --create-namespace   --set image.repository="$IMG" --set image.tag="$TAG"

helm upgrade --install "$REL" charts/ester -n "$NS" --kube-context "$CTX2" --create-namespace   --set image.repository="$IMG" --set image.tag="$TAG"
