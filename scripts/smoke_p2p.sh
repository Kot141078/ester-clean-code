#!/usr/bin/env bash
# -*- coding: utf-8 -*-
: <<'DOC'
scripts/smoke_p2p.sh — dymovoy test P2P-mekhanizma (podpis i API).

Rezhimy:
  --mode simple: Proveryaet podpis odnogo zaprosa (kak v legacy).
  --mode full: Testiruet API (/p2p/bloom/status, /export, /merge).

Primery:
  ESTER_P2P_SECRET=abc python3 scripts/smoke_p2p.sh --mode simple
  BASE_URL=http://localhost:5000 ESTER_P2P_SECRET=abc python3 scripts/smoke_p2p.sh --mode full
  P2P_SIG_LEGACY=1 ESTER_P2P_SECRET=abc python3 scripts/smoke_p2p.sh --mode simple --path /p2p/self/manifest/__smoke__

Mosty:
- Yavnyy (Shell ↔ P2P API): realnye vyzovy s podpisyu cherez p2p_sign.py.
- Skrytyy #1 (Bezopasnost ↔ Praktika): ispolzuet HMAC, kak guard, i legacy X-P2P-Auth.
- Skrytyy #2 (CI ↔ Operatsii): podkhodit dlya lokalnogo testa i CI-pipeline, JSON-otchet.

Zemnoy abzats:
Kak tester provodki: v rezhime simple proveryaet, gorit li lampochka (podpis), v full — vsyu skhemu (API).

c=a+b
DOC

set -euo pipefail

# Konfiguratsiya
BASE_URL="${BASE_URL:-}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
[ -z "$BASE_URL" ] && BASE_URL="http://${HOST}:${PORT}"
SECRET="${ESTER_P2P_SECRET:-}"
P2P_SIG_LEGACY="${P2P_SIG_LEGACY:-0}"
METHOD="${METHOD:-GET}"
PATH_PART="${PATH_PART:-/p2p/self/manifest/__smoke__}"
MODE="${MODE:-simple}"

# Proverka zavisimostey
command -v curl >/dev/null 2>&1 || { echo "[p2p-smoke] ERR: curl not found"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "[p2p-smoke] ERR: python3 not found"; exit 2; }
[ -f "scripts/p2p_sign.py" ] || { echo "[p2p-smoke] ERR: scripts/p2p_sign.py not found"; exit 2; }
command -v jq >/dev/null 2>&1 && HAS_JQ=1 || HAS_JQ=0

if [ -z "$SECRET" ]; then
  echo "[p2p-smoke] ERR: ESTER_P2P_SECRET not set"
  exit 2
fi

# Funktsiya dlya generatsii zagolovkov podpisi
gen_hdrs() {
  local method="$1" path="$2" body="${3:-}"
  if [ "$P2P_SIG_LEGACY" = "1" ]; then
    python3 scripts/p2p_sign.py "$method" "$path" "$body" --secret "$SECRET" 2>/dev/null
  else
    python3 scripts/p2p_sign.py "$method" "$path" "$body" 2>/dev/null
  fi
}

# Funktsiya dlya vypolneniya curl-zaprosa
curl_h() {
  local method="$1" path="$2" body="${3:-}"
  local hdrs
  hdrs=$(gen_hdrs "$method" "$path" "$body") || { echo "[p2p-smoke] ERR: header generation failed"; return 99; }
  # shellcheck disable=SC2086
  eval "curl -s -w '\n%{http_code}' -H $hdrs ${body:+-H 'Content-Type: application/json' -d '${body}'} -X $method \"$BASE_URL$path\""
}

# JSON-otchet
REPORT=$(cat <<EOF
{
  "ok": true,
  "mode": "$MODE",
  "tests": []
}
EOF
)

# Funktsiya dlya dobavleniya rezultata testa v otchet
add_test_result() {
  local name="$1" code="$2" body="$3" error="${4:-}"
  local test_json
  test_json=$(cat <<EOF
{
  "name": "$name",
  "code": "$code",
  "ok": $([ "$code" -ge 200 ] && [ "$code" -lt 300 ] && echo true || echo false),
  "body": $body,
  "error": $([ -n "$error" ] && echo "\"$error\"" || echo null)
}
EOF
)
  REPORT=$(echo "$REPORT" | jq ".tests += [$test_json]")
}

# Rezhim simple
if [ "$MODE" = "simple" ]; then
  echo "[p2p-smoke] Testing signature ($METHOD $PATH_PART)"
  resp=$(curl_h "$METHOD" "$PATH_PART")
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  body_json=$(echo "$body" | jq -c . 2>/dev/null || echo "{}")
  if [ "$code" = "401" ]; then
    add_test_result "signature" "$code" "$body_json" "unauthorized"
    echo "[p2p-smoke] FAIL: 401 unauthorized"
  else
    add_test_result "signature" "$code" "$body_json"
    echo "[p2p-smoke] PASS: code=$code"
  fi
fi

# Rezhim full
if [ "$MODE" = "full" ]; then
  # Test 1: status
  echo "[p2p-smoke] 1) Testing /p2p/bloom/status"
  resp=$(curl_h GET /p2p/bloom/status)
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  body_json=$(if [ "$HAS_JQ" = "1" ]; then echo "$body" | jq -c . 2>/dev/null || echo "{}"; else echo "{}"; fi)
  if ! [[ "$code" =~ ^2 ]]; then
    add_test_result "status" "$code" "$body_json" "non-2xx code"
    echo "[p2p-smoke] FAIL: status code=$code"
  else
    add_test_result "status" "$code" "$body_json"
    echo "[p2p-smoke] PASS: status code=$code"
  fi

  # Test 2: export
  echo "[p2p-smoke] 2) Testing /p2p/bloom/export"
  resp=$(curl_h GET /p2p/bloom/export)
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  body_json=$(if [ "$HAS_JQ" = "1" ]; then echo "$body" | jq -c . 2>/dev/null || echo "{}"; else echo "{}"; fi)
  if ! [[ "$code" =~ ^2 ]]; then
    add_test_result "export" "$code" "$body_json" "non-2xx code"
    echo "[p2p-smoke] FAIL: export code=$code"
    exit 1
  fi
  add_test_result "export" "$code" "$body_json"

  # Izvlechenie parametrov Bloom-filtra
  m=$(echo "$body" | python3 -c 'import sys,json;print((json.load(sys.stdin) or {}).get("m",0))' 2>/dev/null || echo 0)
  k=$(echo "$body" | python3 -c 'import sys,json;print((json.load(sys.stdin) or {}).get("k",0))' 2>/dev/null || echo 0)
  bits=$(echo "$body" | python3 -c 'import sys,json;print((json.load(sys.stdin) or {}).get("bits_hex",""))' 2>/dev/null || echo "")
  payload=$(python3 -c "import json; print(json.dumps({\"m\": $m, \"k\": $k, \"bits_hex\": \"$bits\"}))")

  # Test 3: merge
  echo "[p2p-smoke] 3) Testing /p2p/bloom/merge"
  resp=$(curl_h POST /p2p/bloom/merge "$payload")
  code="${resp##*$'\n'}"
  body="${resp%$'\n'*}"
  body_json=$(if [ "$HAS_JQ" = "1" ]; then echo "$body" | jq -c . 2>/dev/null || echo "{}"; else echo "{}"; fi)
  ok=$(echo "$body" | python3 -c 'import sys,json;print("1" if (json.load(sys.stdin) or {}).get("ok") else "0")' 2>/dev/null || echo "0")
  if ! [[ "$code" =~ ^2 ]] || [ "$ok" != "1" ]; then
    add_test_result "merge" "$code" "$body_json" "non-2xx code or ok=false"
    echo "[p2p-smoke] FAIL: merge code=$code, ok=$ok"
    exit 1
  fi
  add_test_result "merge" "$code" "$body_json"
  echo "[p2p-smoke] PASS: merge code=$code"
fi

# Vyvod JSON-otcheta
echo "$REPORT" | jq .
final_ok=$(echo "$REPORT" | jq '.tests | all(.ok)')
if [ "$final_ok" = "true" ]; then
  echo "[p2p-smoke] OK"
  exit 0
else
  echo "[p2p-smoke] FAILED"
  exit 1
fi