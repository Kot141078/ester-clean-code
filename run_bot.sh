#!/usr/bin/env bash
set -euo pipefail

PY="$HOME/miniconda/envs/ester-gpu/bin/python"
[[ -x "$PY" ]] || PY="$HOME/.conda/envs/ester-gpu/bin/python"
command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python)"

export PYTHONUNBUFFERED=1
export ESTER_API_BASE="${ESTER_API_BASE:-http://127.0.0.1:8010}"

cd /mnt/d/ester-project

# Important: ignore any system proxies in VSL
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy NO_PROXY no_proxy

exec "$PY" - <<'PY'
import os, sys
from dotenv import load_dotenv

# Explicitly loading .env
load_dotenv('/mnt/d/ester-project/.env', override=True)

ester_api = os.getenv('ESTER_API_BASE')
print(f'[run_bot] ESTER_API_BASE={ester_api}', flush=True)

try:
    from config import TELEGRAM_TOKEN
except Exception as e:
    print('Cannot import config:', e, file=sys.stderr)
    raise

from telegram_bot import run_bot

if not TELEGRAM_TOKEN:
    raise SystemExit('TELEGRAM_TOKEN is empty — prover .env')

run_bot(TELEGRAM_TOKEN)
PY
