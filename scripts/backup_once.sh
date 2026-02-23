#!/usr/bin/env bash
set -euo pipefail

BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
ART="artifacts/recovery"
mkdir -p "$ART"

H=( )
[ -n "$JWT" ] && H=(-H "Authorization: Bearer $JWT")

echo "[backup-once] run"
curl -sS -X POST "$BASE/ops/backup/run" "${H[@]}" -H 'Content-Type: application/json' -d '{}' | tee "$ART/1_run.json"

BK=""
if command -v jq >/dev/null 2>&1; then
  BK="$(jq -r '.path // .zip // .backup_path // empty' <"$ART/1_run.json" || true)"
fi

echo "[backup-once] verify"
BODY='{}'; [ -n "$BK" ] && BODY="{\"path\":\"$BK\"}"
curl -sS -X POST "$BASE/ops/backup/verify" "${H[@]}" -H 'Content-Type: application/json' -d "$BODY" | tee "$ART/2_verify.json"

echo "[backup-once] done"
