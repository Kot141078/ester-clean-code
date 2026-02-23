#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
PORT="${PORT:-5000}"
TIMEOUT="${VERIFY_TIMEOUT_SEC:-120}"

H=( ); [ -n "$JWT" ] && H=(-H "Authorization: Bearer $JWT")

echo "[verify-autorestart] BASE=$BASE PORT=$PORT TIMEOUT=$TIMEOUT"

if ! command -v curl >/dev/null 2>&1; then echo "[verify-autorestart] trebuetsya curl" >&2; exit 2; fi
if ! command -v lsof >/dev/null 2>&1; then echo "[verify-autorestart] trebuetsya lsof" >&2; exit 2; fi

echo "[1/4] check health before"
curl -fsS "$BASE/health" "${H[@]}" >/dev/null || echo "[warn] /health ne otvechaet do kill"

echo "[2/4] kill process on :$PORT"
PID="$(lsof -t -i :$PORT || true)"
if [ -z "$PID" ]; then echo "[verify-autorestart] net protsessa na portu $PORT — nechego ubivat."; else kill -9 "$PID" || true; echo "[verify-autorestart] ubit PID=$PID"; fi

echo "[3/4] wait for health up (timeout ${TIMEOUT}s)"
UP=0
for i in $(seq 1 "$TIMEOUT"); do
  if curl -fsS "$BASE/health" "${H[@]}" >/dev/null; then echo "[verify-autorestart] servis podnyalsya za ${i}s"; UP=1; break; fi
  sleep 1
done

echo "[4/4] result"
if [ "$UP" -eq 1 ]; then echo "[verify-autorestart] OK"; exit 0; else echo "[verify-autorestart] FAIL — servis ne podnyalsya za ${TIMEOUT}s" >&2; exit 1; fi
