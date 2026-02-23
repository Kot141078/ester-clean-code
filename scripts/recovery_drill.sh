#!/usr/bin/env bash
set -euo pipefail
BASE="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
JWT="${ESTER_JWT:-}"
ART="artifacts/recovery"
mkdir -p "$ART"

H=( )
[ -n "$JWT" ] && H=(-H "Authorization: Bearer $JWT")

log(){ echo "[drill] $*"; }

log run backup
curl -sS -X POST "$BASE/ops/backup/run" "${H[@]}" -H 'Content-Type: application/json' -d '{}' | tee "$ART/1_run.json"

BK=""
if command -v jq >/dev/null 2>&1; then
  BK="$(jq -r '.path // .zip // .backup_path // empty' <"$ART/1_run.json" || true)"
fi

log verify
BODY='{}'; [ -n "$BK" ] && BODY="{\"path\":\"$BK\"}"
curl -sS -X POST "$BASE/ops/backup/verify" "${H[@]}" -H 'Content-Type: application/json' -d "$BODY" | tee "$ART/2_verify.json"

log simulate loss
curl -sS -X POST "$BASE/ops/simulate/loss" "${H[@]}" -H 'Content-Type: application/json' -d '{"hard":false}' | tee "$ART/3_loss.json" || true

log restore
R_BODY='{}'; [ -n "$BK" ] && R_BODY="{\"path\":\"$BK\"}"
curl -sS -X POST "$BASE/ops/backup/restore" "${H[@]}" -H 'Content-Type: application/json' -d "$R_BODY" | tee "$ART/4_restore.json"

log ok
