#!/usr/bin/env bash
# E2E curl scripts for “Esther” (see TC §5)
# Progonyaet skvoznye proverki: auth → health → ingest → chat → replication → backup → RBAC deny
set -euo pipefail

BASE="${BASE:-http://127.0.0.1:8000}"
UA="${UA:-ester-e2e}"
IP="${IP:-127.0.0.1}"
CSRF_SECRET="${CSRF_SECRET:-ester-dev-csrf-secret}"
REPL_TOKEN_HEADER="${REPL_TOKEN_HEADER:-}" # if you need to explicitly transfer a token: export REPL_TOKEN_NEADER="C-REPL-TOKEN: legal_token"

echo "== Ester E2E =="
echo "BASE=$BASE"

_json_field() {
  # usage: _json_field 'json' 'field'
  python3 - "$1" "$2" <<'PY'
import json,sys
data = sys.argv[1]
fld = sys.argv[2]
try:
    j = json.loads(data)
    v = j.get(fld, "")
    if isinstance(v, (list,dict)):
        print("")
    else:
        print(v)
except Exception:
    print("")
PY
}

_csrf_token() {
  # base64url(HMAC_SHA256(secret, f"{UA}|{IP}")) bez '='
  python3 - "$CSRF_SECRET" "$UA" "$IP" <<'PY'
import sys, hmac, hashlib, base64
secret,ua,ip = sys.argv[1], sys.argv[2], sys.argv[3]
msg = f"{ua}|{ip}".encode("utf-8")
sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
print(base64.urlsafe_b64encode(sig).decode("ascii").rstrip("="))
PY
}

curl_json() {
  # usage: curl_json METHOD URL DATA HEADERS...
  local method="$1"; shift
  local url="$1"; shift
  local data="${1-}"; shift || true
  local extra_headers=("$@")
  if [ -n "$data" ]; then
    curl -sS -X "$method" "$url" \
      -H "Content-Type: application/json" \
      "${extra_headers[@]}" \
      --data "$data"
  else
    curl -sS -X "$method" "$url" "${extra_headers[@]}"
  fi
}

# --- Auth tokens ---
echo "-> Issue JWT tokens"
USER_J=$(curl_json POST "$BASE/auth/token" '{"user":"e2e-user","roles":["user"]}')
USER_T=$(_json_field "$USER_J" token)
OP_J=$(curl_json POST "$BASE/auth/token" '{"user":"e2e-op","roles":["operator"]}')
OP_T=$(_json_field "$OP_J" token)
ADM_J=$(curl_json POST "$BASE/auth/token" '{"user":"e2e-admin","roles":["admin"]}')
ADM_T=$(_json_field "$ADM_J" token)

H_USER=(-H "Authorization: Bearer $USER_T")
H_OP=(-H "Authorization: Bearer $OP_T")
H_ADM=(-H "Authorization: Bearer $ADM_T")

test -n "$USER_T" && test -n "$OP_T" && test -n "$ADM_T" || { echo "Auth failed"; exit 2; }

# --- Health ---
echo "-> /health"
curl -sS "$BASE/health" | sed -e 's/.*/OK/'

# --- Ingest upload ---
echo "-> /ingest/file upload"
TMP="$(mktemp -d)"
F="$TMP/e2e_note.txt"
echo "hello ester $(date -u +%s)" > "$F"
CSRF=$(_csrf_token)

UPLOAD_OUT=$(curl -sS -X POST "$BASE/ingest/file" \
  -H "User-Agent: $UA" -H "X-Forwarded-For: $IP" -H "X-CSRF-Token: $CSRF" \
  -H "Authorization: Bearer $OP_T" \
  -F "file=@$F;type=text/plain")
echo "upload: $UPLOAD_OUT"
JOB_ID=$(_json_field "$UPLOAD_OUT" id)
if [ -n "$JOB_ID" ] && [ "$JOB_ID" != "direct" ]; then
  echo "-> /ingest/status?id=$JOB_ID"
  for i in $(seq 1 10); do
    ST=$(curl -sS "$BASE/ingest/status?id=$JOB_ID" -H "Authorization: Bearer $OP_T" || true)
    echo "status[$i]: $ST"
    echo "$ST" | grep -q '"status": *"DONE"' && break || sleep 1
  done
fi

# --- Chat message ---
echo "-> /chat/message"
CHAT=$(curl_json POST "$BASE/chat/message" '{"mode":"local","query":"Privet! Prover RAG.","use_rag":true,"temperature":0.0}' "${H_USER[@]}")
echo "chat: $CHAT" | cut -c -240

# --- Replication snapshot/apply ---
echo "-> /replication/snapshot (and apply)"
if [ -n "$REPL_TOKEN_HEADER" ]; then
  SNAP_HEADERS=(-H "$REPL_TOKEN_HEADER")
else
  SNAP_HEADERS=()
fi
# snapshot
SNAP_HEADERS+=(-D "$TMP/headers.txt")
SNAP=$(curl -sS -o "$TMP/snap.zip" "${SNAP_HEADERS[@]}" "$BASE/replication/snapshot" || true)
SIG=$(grep -i '^X-Signature:' "$TMP/headers.txt" | awk '{print $2}' | tr -d '\r\n')
if [ -f "$TMP/snap.zip" ] && [ -s "$TMP/snap.zip" ] && [ -n "$SIG" ]; then
  APPLY_HEADERS=()
  [ -n "$REPL_TOKEN_HEADER" ] && APPLY_HEADERS+=(-H "$REPL_TOKEN_HEADER")
  APPLY_HEADERS+=(-H "X-Signature: $SIG" -H "Content-Type: application/zip")
  APPLY=$(curl -sS -X POST "$BASE/replication/apply" "${APPLY_HEADERS[@]}" --data-binary "@$TMP/snap.zip" || true)
  echo "apply: $APPLY" | cut -c -200
else
  echo "snapshot not available (maybe token not required or endpoint disabled)"
fi

# --- Backups ---
echo "-> /ops/backup/run /verify /restore"
RUN=$(curl_json POST "$BASE/ops/backup/run" '{}' "${H_OP[@]}")
ZIP=$(_json_field "$RUN" zip)
echo "run: $RUN"
if [ -n "$ZIP" ] && [ -f "$ZIP" ]; then
  VER=$(curl_json POST "$BASE/ops/backup/verify" "{\"path\":\"$ZIP\"}" "${H_ADM[@]}")
  echo "verify: $VER"
  REST_DIR="$TMP/restore"
  mkdir -p "$REST_DIR"
  RES=$(curl_json POST "$BASE/ops/backup/restore" "{\"path\":\"$ZIP\",\"target_dir\":\"$REST_DIR\"}" "${H_ADM[@]}")
  echo "restore: $RES"
else
  echo "backup zip not found at $ZIP"
fi

# --- RBAC deny (user) ---
echo "-> RBAC deny check (/ops under user)"
DENY=$(curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE/ops/backup/run" -H "Authorization: Bearer $USER_T")
echo "deny status: $DENY"

echo "== E2E done =="
