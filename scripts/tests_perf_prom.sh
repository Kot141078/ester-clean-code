#!/usr/bin/env bash
set -euo pipefail
export ESTER_BASE_URL="${ESTER_BASE_URL:-http://localhost:5000}"
export METRICS_PATH="/metrics/prom"
echo "[perf-prom] Using ${ESTER_BASE_URL}${METRICS_PATH}"
pytest -m perf -k metrics -q
