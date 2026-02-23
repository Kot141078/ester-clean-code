#!/usr/bin/env bash
set -euo pipefail
if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
  echo "Set TELEGRAM_BOT_TOKEN first"
  exit 1
fi
python3 telegram_bot.py
