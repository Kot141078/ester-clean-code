#!/usr/bin/env bash
set -euo pipefail
BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
INTERVAL="${INTERVAL_SEC:-1}"
TIMEOUT="${TIMEOUT_SEC:-3}"
ART="artifacts/recovery"
mkdir -p "$ART"
LOG="$ART/health_watchdog.log"

H=( ); [ -n "$JWT" ] && H=(-H "Authorization: Bearer $JWT")
echo "[watchdog] start $(date -Iseconds) BASE=$BASE" | tee -a "$LOG"

DOWN_START=""
while true; do
  TS="$(date -Iseconds)"
  if curl -fsS --max-time "$TIMEOUT" "$BASE/health" "${H[@]}" >/dev/null 2>&1; then
    if [ -n "$DOWN_START" ]; then
      echo "[$TS] UP (downtime was from $DOWN_START)" | tee -a "$LOG"; DOWN_START=""
    fi
  else
    if [ -z "$DOWN_START" ]; then DOWN_START="$TS"; echo "[$TS] DOWN" | tee -a "$LOG"; fi
  fi
  sleep "$INTERVAL"
done
