#!/usr/bin/env bash
# R1/tests/fixtures/curl_tg_link.sh — ruchnaya proverka /link cherez webhook (curl)
# Mosty:
# - Yavnyy: Enderton — predikaty (sekret prinyat, JSON korrekten).
# - Skrytyy #1: Ashbi — minimalnyy regulyator (odin POST — dostatochno).
# - Skrytyy #2: Cover & Thomas — minimalnyy «signal» razlichaet sostoyaniya (prinyat/otvergnut).
# Zemnoy abzats: udobno rukami debazhit webhook bez podnyatogo bota; JSON sobiraetsya na letu.
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
