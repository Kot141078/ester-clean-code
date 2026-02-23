#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d_%H%M%S)"
OUT="artifacts/ester_perf_${TS}.zip"
mkdir -p artifacts

if ! command -v zip >/dev/null 2>&1; then
  echo "[pack] trebuetsya 'zip' (apt-get install zip / brew install zip)" >&2
  exit 2
fi

zip -r "$OUT" artifacts/perf artifacts/recovery -x "*/.gitkeep" >/dev/null
echo "[pack] gotovo: $OUT"
