#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
RPS="${K6_RPS:-10}"
DUR="${K6_DURATION:-2m}"
VUS="${K6_VUS:-20}"
ART="artifacts/perf"
mkdir -p "$ART"

if ! command -v k6 >/dev/null 2>&1; then
  echo "[bench] k6 ne nayden. Ustanovi: https://k6.io/docs/get-started/installation/" >&2
  exit 2
fi

export ESTER_BASE_URL="$BASE" ESTER_JWT="$JWT" K6_DURATION="$DUR" K6_VUS="$VUS" K6_RPS="$RPS"

k6 run --summary-export "$ART/read.summary.json" tests/perf/k6_read.js
k6 run --summary-export "$ART/replicate.summary.json" tests/perf/k6_replicate.js

cat >"$ART/report.md" <<EOF
# Perf report
- Base: $BASE
- Duration: $DUR, VUs: $VUS, RPS: $RPS
- Summaries: read.summary.json, replicate.summary.json
EOF

echo "[bench] Gotovo: smotri $ART"
