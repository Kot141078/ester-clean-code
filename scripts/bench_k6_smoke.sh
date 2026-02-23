#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
export ESTER_BASE_URL="$BASE" ESTER_JWT="$JWT"

ART="artifacts/perf"
mkdir -p "$ART"

export K6_RPS="${K6_RPS:-5}"
export K6_DURATION="${K6_DURATION:-30s}"
export K6_VUS="${K6_VUS:-5}"

if ! command -v k6 >/dev/null 2>&1; then
  echo "[bench-smoke] k6 ne nayden. Ustanovi: scripts/k6_install_local.sh" >&2
  exit 2
fi

echo "[bench-smoke] read..."
k6 run --summary-export "$ART/read.smoke.summary.json" tests/perf/k6_read.js

echo "[bench-smoke] replicate..."
k6 run --summary-export "$ART/replicate.smoke.summary.json" tests/perf/k6_replicate.js

python3 scripts/perf_aggregate.py || true

echo "[bench-smoke] done. artifacts in $ART"
