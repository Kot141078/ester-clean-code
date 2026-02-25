#!/usr/bin/env bash
# Podpis konteynernogo obraza cosign.
# Ispolzovanie:
#   COSIGN_EXPERIMENTAL=1 ./scripts/sign_cosign.sh ghcr.io/owner/repo:tag
# Support key and keyless modes:
#   COSIGN_KEY_PATH=/path/to/cosign.key COSIGN_PASSWORD=... ./scripts/sign_cosign.sh <image>
set -euo pipefail

if ! command -v cosign >/dev/null 2>&1; then
  echo "[cosign] cosign ne nayden. Ustanovite: https://github.com/sigstore/cosign" >&2
  exit 2
fi

IMAGE="${1:-}"
if [[ -z "$IMAGE" ]]; then
  echo "Ispolzovanie: $0 <image-ref>" >&2
  exit 2
fi

if [[ -n "${COSIGN_KEY_PATH:-}" ]]; then
  echo "[cosign] rezhim klyuchevoy podpisi (key file)"
  cosign sign --key "${COSIGN_KEY_PATH}" "${IMAGE}"
else
  echo "[cosign] rezhim keyless (OIDC). Ubedites, chto COSIGN_EXPERIMENTAL=1"
  export COSIGN_EXPERIMENTAL="${COSIGN_EXPERIMENTAL:-1}"
  cosign sign --yes --rekor-url https://rekor.sigstore.dev "${IMAGE}"
fi

echo "[cosign] Podpis uspeshno vypolnena dlya ${IMAGE}"
