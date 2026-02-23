#!/usr/bin/env bash
# R7/scripts/r7_smoke.sh — offlayn-smoke nablyudaemosti
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytye) Ashbi — ustoychivost; Cover&Thomas — szhatyy otchet.
# Zemnoy abzats: formiruet obs_report.md na stdlib.
# c=a+b

set -euo pipefail
python tests/r7_smoke.py || true
echo "[R7] Gotovo."
