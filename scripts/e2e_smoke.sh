#!/usr/bin/env bash
set -euo pipefail

# E2E smoke dlya «Zhelezobeton».
# Trebovaniya: curl, jq. Server uzhe podnyat lokalno etim zhe job'om.
# Autentifikatsiya:
#  - Esli zadan ADMIN_JWT — ispolzuem ego.
#  - Inache pytaemsya poluchit token cherez /auth/login (esli ENABLE_SIMPLE_LOGIN=1).

BASE_URL="${BASE_URL:-http://127.0.0.1:${PORT:-8080}}"
CURL="curl -fsS"
JQ="jq -r"

log() { echo "[$(date +%H:%M:%S)] $*" >&2; }

get_admin_jwt() {
  if [[ -n "${ADMIN_JWT:-}" ]]; then
    echo "$ADMIN_JWT"; return 0
  fi
  # Popytka dev-logina
  if $CURL -X POST "$BASE_URL/auth/login" -H 'Content-Type: application/json' \
      -d '{"user":"ci","role":"admin"}' >/tmp/login.json 2>/dev/null; then
    tok="$(cat /tmp/login.json | $JQ '.access_token' || true)"
    if [[ "$tok" != "null" && -n "$tok" ]]; then
      echo "$tok"; return 0
    fi
  fi
  echo ""
}

get_user_jwt() {
  if $CURL -X POST "$BASE_URL/auth/login" -H 'Content-Type: application/json' \
      -d '{"user":"ciuser","role":"user"}' >/tmp/login_user.json 2>/dev/null; then
    tok="$(cat /tmp/login_user.json | $JQ '.access_token' || true)"
    if [[ "$tok" != "null" && -n "$tok" ]]; then
      echo "$tok"; return 0
    fi
  fi
  echo ""
}

require_code() {
  local expected="$1"; shift
  local name="$1"; shift
  local code
  set +e
  code=$(curl -o /dev/null -s -w "%{http_code}" "$@")
  set -e
  if [[ "$code" != "$expected" ]]; then
    echo "FAIL: $name => expected $expected, got $code" >&2
    exit 1
  fi
  log "OK: $name ($expected)"
}

require_200() { require_code "200" "$@"; }
require_403() { require_code "403" "$@"; }
require_401() { require_code "401" "$@"; }

log "Base: $BASE_URL"

# 0) /health ili /live
if $CURL "$BASE_URL/health" >/dev/null 2>&1; then
  require_200 "health" "$BASE_URL/health"
else
  require_200 "live" "$BASE_URL/live"
fi

# 1) Admin JWT
ADMIN_JWT="$(get_admin_jwt || true)"
if [[ -z "$ADMIN_JWT" ]]; then
  echo "FAIL: no ADMIN_JWT and /auth/login unavailable. Provide ADMIN_JWT env or enable /auth/login." >&2
  exit 1
fi

# 2) /portal pod adminom (proveryaem, chto UI otdaetsya)
require_200 "portal (admin)" -H "Authorization: Bearer $ADMIN_JWT" "$BASE_URL/portal"

# 3) mTLS whoami: imitiruem zagolovki ot ingress
require_200 "mtls whoami" \
  -H "X-Client-Verified: SUCCESS" \
  -H "X-Client-DN: CN=node-1,OU=core,O=Ester" \
  "$BASE_URL/mtls/whoami"

# 4) RBAC: pod user rolyu /ops/* dolzhen dat 403
USER_JWT="$(get_user_jwt || true)"
if [[ -n "$USER_JWT" ]]; then
  require_403 "RBAC deny /ops as user" -H "Authorization: Bearer $USER_JWT" "$BASE_URL/ops/secure_ping" \
    -H "X-Client-Verified: SUCCESS" -H "X-Client-DN: CN=ops-1,OU=ops,O=Ester"
else
  log "WARN: no user JWT (dev login disabled). Skipping RBAC user check."
fi

# 5) P2P echo pod podpisyu (esli zaschischeno p2p_guard'om, potrebuetsya X-P2P-*)
ts="$(date +%s)"
sig="$(python - <<'PY'
import os,hashlib,hmac,time,sys
secret=os.environ.get("ESTER_P2P_SECRET","")
ts=str(int(time.time()))
def h(b): return hashlib.sha256(b).hexdigest()
msg=f"{ts}\nGET\n/p2p/echo\n{h(b'')}".encode()
print(ts+" "+(hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest() if secret else ""))
PY
)"
ts_header="$(echo "$sig" | awk '{print $1}')"
sig_hex="$(echo "$sig" | awk '{print $2}')"
if [[ -n "${ESTER_P2P_SECRET:-}" && -n "$sig_hex" ]]; then
  require_200 "p2p echo signed" \
    -H "X-P2P-Ts: ${ts_header}" \
    -H "X-P2P-Node: node-1" \
    -H "X-P2P-Signature: ${sig_hex}" \
    "$BASE_URL/p2p/echo"
else
  log "INFO: ESTER_P2P_SECRET not set; skipping /p2p/echo signed check."
fi

# 6) Replikatsiya: replicator dopuskaetsya, ops zapreschen
require_200 "replication snapshot (replicator)" \
  -H "X-Client-Verified: SUCCESS" \
  -H "X-Client-DN: CN=node-1,OU=core,O=Ester" \
  "$BASE_URL/replication/test_snapshot"

require_403 "replication snapshot (ops denied)" \
  -H "X-Client-Verified: SUCCESS" \
  -H "X-Client-DN: CN=ops-1,OU=ops,O=Ester" \
  "$BASE_URL/replication/test_snapshot"

# 7) OPS secure ping: dostupen tolko ops po mTLS
require_200 "ops secure_ping (ops)" \
  -H "X-Client-Verified: SUCCESS" \
  -H "X-Client-DN: CN=ops-1,OU=ops,O=Ester" \
  "$BASE_URL/ops/secure_ping"

require_403 "ops secure_ping (node denied)" \
  -H "X-Client-Verified: SUCCESS" \
  -H "X-Client-DN: CN=node-1,OU=core,O=Ester" \
  "$BASE_URL/ops/secure_ping"

log "E2E smoke PASSED."
