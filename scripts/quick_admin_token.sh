#!/usr/bin/env bash
# С0/skripts/kisk_admin_token.sh - generate admin-ZhVT and check /admin (curl)
# Bridges: (Explicit) Enderton - simple test predicates; (Hidden) Ashby - the regulator is simpler than the system; Janes - likelihood of session validity.
# Earthly paragraph: helps to quickly locally verify that the RVACH/GVT is “breathing” without UI. Dependencies: pothon, curl.
# c=a+b

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
USER_NAME="${USER_NAME:-Owner}"
ROLE="${ROLE:-admin}"
TTL="${TTL:-600}"

if [ -z "${JWT_SECRET:-}" ]; then
  echo "[quick_admin_token] WARN: JWT_SECRET ne zadan, ispolzuyu 'devsecret' (NE dlya proda)."
  export JWT_SECRET="devsecret"
fi

TOKEN="$(python tools/jwt_mint.py --user "$USER_NAME" --role "$ROLE" --ttl "$TTL")"
echo "[quick_admin_token] JWT: ${TOKEN:0:24}…"

set +e
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE_URL/admin")
set -e

echo "[quick_admin_token] /admin => HTTP $HTTP_CODE"
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
  echo "[quick_admin_token] OK"
else
  echo "[quick_admin_token] WARN: /admin vernul $HTTP_CODE — prover RBAC/JWT_SECRET/prilozhenie."
fi
