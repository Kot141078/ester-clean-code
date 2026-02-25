#!/usr/bin/env bash
# C0/tesc/fixtures/curl_webhook.sh - manual POST in Telegram webhook (curl)
# Mosty: (Yavnyy) Enderton — proveryaemyy predikat “sekret zagolovka prinyat”; (Skrytye) Ashbi — minimalnyy regulyator; Dzheynes - nablyudenie povyshaet pravdopodobie “put rabotaet.”
# Ground paragraph: helps you check the route with your hands without a raised bot; JSION fixture is taken from test/fixtures/tg_update.zsion.
# c=a+b

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
SECRET="${TELEGRAM_WEBHOOK_SECRET:-devhook}"
PAYLOAD_FILE="${PAYLOAD_FILE:-tests/fixtures/tg_update.json}"

if [ ! -f "$PAYLOAD_FILE" ]; then
  echo "Fayl ne nayden: $PAYLOAD_FILE" >&2
  exit 1
fi

curl -i \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: $SECRET" \
  --data @"$PAYLOAD_FILE" \
  "$BASE_URL/api/telegram/webhook"
