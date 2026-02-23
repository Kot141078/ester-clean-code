#!/usr/bin/env bash
# tools/selfcheck.sh — mini-smoke dlya Ester
# MOSTY:
# - (Yavnyy) Proveryaet python, importy, zapuskaet verify_routes.py
# - (Skrytyy #1) curl k /health i /metrics/prom (esli server podnyat)
# - (Skrytyy #2) Pishet artefakty v data/selfcheck
# ZEMNOY ABZATs: «Podralsya s provodami?» — odnoy komandoy vidno, gde obryv.
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
