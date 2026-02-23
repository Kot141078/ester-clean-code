#!/usr/bin/env bash
set -euo pipefail
APP_URL="${APP_URL:-http://localhost:5000}"

echo "Minting JWTs..."
ADMIN=$(python scripts/mint_jwt.py admin)
OPERATOR=$(python scripts/mint_jwt.py operator)
USER=$(python scripts/mint_jwt.py user)
NOAUTH=""

function req() {
  local method="$1"; shift
  local path="$1"; shift
  local token="$1"; shift
  local code
  if [ -n "$token" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" -H "Authorization: Bearer $token" "$APP_URL$path")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$APP_URL$path")
  fi
  printf "%-6s %-28s -> %s\n" "$method" "$path" "$code"
}

echo "=== PUBLIC ==="
req GET /health "$NOAUTH"
req GET /metrics "$NOAUTH"

echo "=== CHAT (USER allowed) ==="
req POST /chat "$USER"
req POST /chat "$OPERATOR"
req POST /chat "$ADMIN"
req POST /chat "$NOAUTH"

echo "=== INGEST ==="
req POST /ingest/file "$ADMIN"
req POST /ingest/file "$OPERATOR"
req POST /ingest/file "$USER"
req POST /ingest/file "$NOAUTH"
req GET  /ingest/status?id=foo "$ADMIN"
req GET  /ingest/status?id=foo "$USER"

echo "=== PROVIDERS ==="
req GET  /providers/status "$ADMIN"
req GET  /providers/status "$USER"
req POST /providers/select "$OPERATOR"

echo "=== OPS/BACKUP ==="
req POST /ops/backup/run "$OPERATOR"
req POST /ops/backup/run "$USER"
req POST /ops/backup/restore "$ADMIN"
req POST /ops/backup/restore "$OPERATOR"

echo "=== P2P ==="
req GET  /p2p/status "$OPERATOR"
req GET  /p2p/status "$USER"
req POST /p2p/pull_now "$OPERATOR"
