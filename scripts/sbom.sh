#!/usr/bin/env bash
# SNOM generation using software.
# Varianty:
#   ./scripts/sbom.sh image ghcr.io/owner/repo:tag
#   ./scripts/sbom.sh dir .
set -euo pipefail

if ! command -v syft >/dev/null 2>&1; then
  echo "[sbom] syft ne nayden. Ustanovite: https://github.com/anchore/syft" >&2
  exit 2
fi

MODE="${1:-}"
TARGET="${2:-}"

if [[ -z "$MODE" || -z "$TARGET" ]]; then
  echo "Ispolzovanie: $0 <image|dir> <ref>" >&2
  exit 2
fi

STAMP="$(date +%Y%m%d%H%M%S)"

case "$MODE" in
  image)
    IMG="$TARGET"
    SAFE_TAG="$(echo "$IMG" | tr '/:@' '____')"
    OUT="sbom-${SAFE_TAG}-${STAMP}.spdx.json"
    echo "[sbom] image: $IMG -> $OUT"
    syft "registry:${IMG}" -o spdx-json > "$OUT"
    ;;
  dir)
    DIR="$TARGET"
    OUT="sbom-dir-$(basename "$DIR")-${STAMP}.spdx.json"
    echo "[sbom] dir: $DIR -> $OUT"
    syft "dir:${DIR}" -o spdx-json > "$OUT"
    ;;
  *)
    echo "Neizvestnyy rezhim: $MODE (ozhidalos: image|dir)" >&2
    exit 2
    ;;
esac

echo "[sbom] OK: $OUT"
