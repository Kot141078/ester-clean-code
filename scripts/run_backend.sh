#!/usr/bin/env bash
set -euo pipefail
export FLASK_APP=app.py
export PORT="${PORT:-8000}"
export HOST="${HOST:-0.0.0.0}"
python3 - <<'PY'
from app import create_app
app = create_app()
app.run(host="0.0.0.0", port=int(__import__("os").getenv("PORT","8000")))
PY
