#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
DIR="${ESTER_JOURNAL_DIR:-data/journal}"
LIMIT="${REPLAY_LIMIT:-0}"
SLEEP="${REPLAY_SLEEP:-0.01}"

H=( -H 'Content-Type: application/json' )
[ -n "$JWT" ] && H+=(-H "Authorization: Bearer $JWT")

count=0
shopt -s nullglob
for f in "$DIR"/*.jsonl; do
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^\{ ]] || continue
    curl -sS -X POST "$BASE/events/publish" "${H[@]}" -d "$line" >/dev/null || true
    count=$((count+1))
    if [ "$LIMIT" -gt 0 ] && [ "$count" -ge "$LIMIT" ]; then
      echo "[replay] limit $LIMIT reached"
      echo "[replay] posted: $count"
      exit 0
    fi
    sleep "$SLEEP"
  done <"$f"
done
echo "[replay] posted: $count"
