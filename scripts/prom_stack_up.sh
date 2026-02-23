#!/usr/bin/env bash
set -euo pipefail
docker compose -f docker-compose.prom.yml up -d
echo "[prom] up: http://127.0.0.1:9090"
