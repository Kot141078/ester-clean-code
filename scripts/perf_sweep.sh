#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
DUR="${K6_DURATION:-1m}"
RPS_LIST=${SWEEP_RPS:-"5 10 20 40"}
VUS_LIST=${SWEEP_VUS:-"10 20 40"}
ART="artifacts/perf"
mkdir -p "$ART"

if ! command -v k6 >/dev/null 2>&1; then
  echo "[sweep] k6 ne nayden. Ustanovi: https://k6.io/docs/get-started/installation/" >&2
  exit 2
fi

for VUS in $VUS_LIST; do
  for RPS in $RPS_LIST; do
    TS=$(date +%Y%m%d_%H%M%S)
    export ESTER_BASE_URL="$BASE" ESTER_JWT="$JWT" K6_DURATION="$DUR" K6_VUS="$VUS" K6_RPS="$RPS"
    OUT="$ART/read.vus${VUS}.rps${RPS}.${TS}.summary.json"
    echo "[sweep] read: VUS=$VUS RPS=$RPS DUR=$DUR -> $OUT"
    k6 run --summary-export "$OUT" tests/perf/k6_read.js
  done
done

python3 scripts/perf_aggregate.py || true
echo "[sweep] gotovo. smotri $ART"
