#!/usr/bin/env bash
set -euo pipefail
# Carry out a long ingest/upload and kill the API process in the middle, then wait for auto-recovery and log.
BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
PORT="${PORT:-5000}"
ART="artifacts/recovery"
mkdir -p "$ART"
LOG="$ART/chaos_during_ingest_$(date +%Y%m%d_%H%M%S).log"
HJSON=(-H 'Content-Type: application/json'); [ -n "$JWT" ] && HJSON+=(-H "Authorization: Bearer $JWT")

exec > >(tee -a "$LOG") 2>&1

echo "[chaos-during] start $(date -Iseconds) BASE=$BASE PORT=$PORT"
echo "[step] start long ingest"
( for i in $(seq 1 50); do
    sz=$((64*1024)); txt=$(python3 - <<'PY'
print('x'*65536)
PY
)
    curl -sS -X POST "$BASE/ingest/text" "${HJSON[@]}" -d "{"id":"$RANDOM","text":"${txt}","meta":{"i":$i}}" >/dev/null || true
    sleep 0.1
  done ) &
ING_PID=$!
sleep 2
echo "[step] kill process on :$PORT"
bash scripts/chaos_kill.sh || true
echo "[step] wait autorestart"
bash scripts/verify_autorestart.sh || true
wait "$ING_PID" || true
echo "[done] chaos-during completed"
