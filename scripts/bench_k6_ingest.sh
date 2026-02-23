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
  echo "[bench-ingest] k6 ne nayden. Ustanovi: https://k6.io/docs/get-started/installation/" >&2
  exit 2
fi

export ESTER_BASE_URL="$BASE" ESTER_JWT="$JWT" K6_DURATION="$DUR" K6_VUS="$VUS" K6_RPS="$RPS"

k6 run --summary-export "$ART/ingest.summary.json" tests/perf/k6_ingest.js

{
  echo "# Perf report (ingest)"
  echo "- Base: $BASE"
  echo "- Duration: $DUR, VUs: $VUS, RPS: $RPS"
  echo "- Summary: ingest.summary.json"
} > "$ART/report_ingest.md"

echo "[bench-ingest] Gotovo: smotri $ART"
