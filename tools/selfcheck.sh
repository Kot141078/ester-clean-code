#!/usr/bin/env bash
# tools/selfchesk.sh - mini-smoke for Esther
# MOSTY:
# - (Explicit) Checks pothon, imports, runs verifs_rutes.po
# - (Hidden #1) curl to /healthtn and /matrix/prom (if the server is up)
# - (Hidden #2) Writes artifacts to data/selfcheck
# EARTHLY Paragraph: “Fought with the wires?” — with one command you can see where the break is.
# c=a+b
set -euo pipefail

echo "[selfcheck] Python: $(python -V || true)"
mkdir -p data/selfcheck || true

echo "[selfcheck] verify_routes.py ..."
python verify_routes.py || true

if command -v curl >/dev/null 2>&1; then
  echo "[selfcheck] curl /health ..."
  curl -s http://127.0.0.1:8000/health || true
  echo
  echo "[selfcheck] curl /metrics/prom ..."
  curl -s http://127.0.0.1:8000/metrics/prom || true
  echo
fi

echo "[selfcheck] done; see data/selfcheck/report.json"
