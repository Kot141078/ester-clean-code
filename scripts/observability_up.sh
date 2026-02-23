#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.observability.yml}"

echo "[obs] Using compose file: ${COMPOSE_FILE}"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "[obs] ERROR: compose file not found: ${COMPOSE_FILE}" >&2
  exit 1
fi

docker compose -f "${COMPOSE_FILE}" up -d

echo "[obs] Prometheus -> http://localhost:9090"
echo "[obs] Grafana    -> http://localhost:3000 (admin / admin)"
echo "[obs] OTLP       -> grpc:4317, http:4318"

echo "[obs] Checking scrape to Ester /metrics..."
set +e
code="$(curl -sk -o /dev/null -w "%{http_code}" http://localhost:5000/metrics)"
set -e
echo "[obs] GET http://localhost:5000/metrics -> ${code} (non-fatal)"

echo "[obs] Done."
