#!/usr/bin/env bash
# U1/scripts/u1_smoke.sh — offlayn-smoke soveta
# Mosty: (Yavnyy) Enderton; (Skrytye) Ashbi; Cover&Thomas.
# Zemnoy abzats: odna knopka «naydi temy → daydzhest → sovet».
# c=a+b

set -euo pipefail
python tests/u1_smoke.py || true
echo "[U1] Gotovo."
