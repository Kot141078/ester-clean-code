#!/usr/bin/env bash
set -euo pipefail
PORT="${PORT:-5000}"
if ! command -v lsof >/dev/null 2>&1; then
  echo "[chaos] trebuetsya lsof" >&2
  exit 2
fi
pid=$(lsof -t -i :$PORT || true)
if [ -z "$pid" ]; then
  echo "[chaos] net protsessov na portu $PORT"; exit 0; fi
kill -9 "$pid"
echo "[chaos] ubil PID=$pid na portu $PORT"
