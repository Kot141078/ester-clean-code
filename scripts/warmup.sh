#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"

HGET=( ); HJSON=( -H 'Content-Type: application/json' )
[ -n "$JWT" ] && HGET=(-H "Authorization: Bearer $JWT")
[ -n "$JWT" ] && HJSON+=(-H "Authorization: Bearer $JWT")

echo "[warmup] GET /health"; curl -fsS "$BASE/health" "${HGET[@]}" >/dev/null || true
echo "[warmup] GET /routes"; curl -fsS "$BASE/routes" "${HGET[@]}" >/dev/null || true
echo "[warmup] GET /providers/status"; curl -fsS "$BASE/providers/status" "${HGET[@]}" >/dev/null || true
echo "[warmup] POST /events/publish"; now=$(date +%s); curl -fsS -X POST "$BASE/events/publish" "${HJSON[@]}" -d "{"kind":"warmup","payload":{"ts":$now}}" >/dev/null || true
echo "[warmup] done"
