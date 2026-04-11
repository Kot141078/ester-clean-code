#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${ESTER_REPO_ROOT:-$SCRIPT_DIR}"

PY="$HOME/miniconda/envs/ester-gpu/bin/python"
[[ -x "$PY" ]] || PY="$HOME/.conda/envs/ester-gpu/bin/python"
command -v "$PY" >/dev/null 2>&1 || PY="$(command -v python)"

cd "$REPO_ROOT"

PORT="${PORT:-8010}"             # defolt teper 8010
export PORT
export ESTER_PORT="$PORT"        # a separate variable that Flask now looks at
export FLASK_DEBUG="${FLASK_DEBUG:-0}"
export DEBUG="${DEBUG:-0}"
export ESTER_DEBUG="${ESTER_DEBUG:-$DEBUG}"

echo "[run_backend] Using python: $PY"
echo "[run_backend] PORT=$PORT FLASK_DEBUG=$FLASK_DEBUG DEBUG=$DEBUG"

exec "$PY" "$REPO_ROOT/serve_no_reload.py"
