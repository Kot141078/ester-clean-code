#!/usr/bin/env bash
# S0/tests/fixtures/curl_webhook.sh — ruchnoy POST v Telegram webhook (curl)
# Mosty: (Yavnyy) Enderton — proveryaemyy predikat «sekret zagolovka prinyat»; (Skrytye) Ashbi — minimalnyy regulyator; Dzheynes — nablyudenie povyshaet pravdopodobie «put rabotaet».
# Zemnoy abzats: pomogaet rukami proverit marshrut bez podnyatogo bota; JSON fikstura beretsya iz tests/fixtures/tg_update.json.
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
