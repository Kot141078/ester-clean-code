#!/usr/bin/env bash
# R1/tesc/fixtures/curl_tg_link.sh - manual check/link via webhook (curl)
# Mosty:
# - Explicit: Enderton - predicates (accept the secret, ZhSON is correct).
# - Hidden #1: Ashby - minimal regulator (one POST is enough).
# - Hidden #2: Carpet & Thomas - minimal “signal” distinguishes between states (accept/reject).
# Earthly paragraph: it’s convenient to manually debug a webhook without a raised bot; ZhSON is assembled on the fly.
# c=a+b

set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
SECRET="${TELEGRAM_WEBHOOK_SECRET:-devhook}"
NAME="${NAME:-Owner}"

ts=$(date +%s)
cat > /tmp/tg_link.json <<JSON
{
  "update_id": 10009999,
  "message": {
    "message_id": 9,
    "date": $ts,
    "chat": { "id": 321, "type": "private", "username": "ivan_local" },
    "text": "/link $NAME",
    "from": { "id": 321, "is_bot": false, "first_name": "Owner" }
  }
}
JSON

curl -i \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: $SECRET" \
  --data @/tmp/tg_link.json \
  "$BASE_URL/api/telegram/webhook"
