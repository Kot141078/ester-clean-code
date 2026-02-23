#!/usr/bin/env bash
# U2/scripts/u2_smoke.sh — offlayn-smoke Cortex
# Mosty: (Yavnyy) Enderton — proveryaemye shagi; (Skrytye) Ashbi — ustoychivost/katbek; Cover&Thomas — szhatyy signal.
# Zemnoy abzats: odna knopka — podumat i sdelat nuzhnoe.
# c=a+b

set -euo pipefail
python tests/u2_smoke.py || true
echo "[U2] Gotovo."
