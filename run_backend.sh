#!/usr/bin/env bash
set -euo pipefail

PY="$HOME/miniconda/envs/ester-gpu/bin/python"
[[ -x "$PY" ]] || PY="$HOME/.conda/envs/ester-gpu/bin/python"
command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python)"

cd /mnt/d/ester-project

PORT="${PORT:-8010}"             # defolt teper 8010
export PORT
export ESTER_PORT="$PORT"        # otdelnaya peremennaya, na kotoruyu Flask teper smotrit
export FLASK_DEBUG="${FLASK_DEBUG:-0}"
export DEBUG="${DEBUG:-0}"
export ESTER_DEBUG="${ESTER_DEBUG:-$DEBUG}"

echo "[run_backend] Using python: $PY"
echo "[run_backend] PORT=$PORT FLASK_DEBUG=$FLASK_DEBUG DEBUG=$DEBUG"

exec "$PY" /mnt/d/ester-project/serve_no_reload.py
