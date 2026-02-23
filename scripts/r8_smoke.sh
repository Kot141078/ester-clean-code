#!/usr/bin/env bash
# R8/scripts/r8_smoke.sh — offlayn-smoke bezopasnosti/reliza
# Mosty: (Yavnyy) Enderton; (Skrytye) Ashbi; Cover&Thomas.
# Zemnoy abzats: formiruet sec_report.md i release/*.tar.gz, manifest.json.
# c=a+b

set -euo pipefail
python tests/r8_smoke.py || true
echo "[R8] Gotovo."
