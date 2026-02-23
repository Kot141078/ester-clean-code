#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${ESTER_BASE_URL:-http://localhost:5000}"
METRICS_PATH="${METRICS_PATH:-/metrics}"
READY_PATHS=("/ready" "/live" "/health")

echo "[e2e] Using BASE_URL=${BASE_URL}"

ok=0
for p in "${READY_PATHS[@]}"; do
  url="${BASE_URL%/}$p"
  code="$(curl -sk -o /dev/null -w "%{http_code}" "$url" || true)"
  echo "[e2e] GET $url -> $code"
  if [[ "$code" == "200" ]]; then ok=1; fi
done
if [[ "$ok" != "1" ]]; then
  echo "[e2e] ERROR: none of ${READY_PATHS[*]} returned 200" >&2
  exit 1
fi

mpath="${BASE_URL%/}${METRICS_PATH}"
mcode="$(curl -sk -o /dev/null -w "%{http_code}" "$mpath" || true)"
echo "[e2e] GET $mpath -> $mcode"
if [[ "$mcode" != "200" ]]; then
  echo "[e2e] ERROR: ${METRICS_PATH} returned $mcode" >&2
  exit 2
fi

echo "[e2e] OK"
