#!/usr/bin/env bash
set -euo pipefail
docker compose -f docker-compose.prom.yml down -v
echo "[prom] down"
