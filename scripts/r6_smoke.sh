#!/usr/bin/env bash
# R6/scripts/r6_smoke.sh — offlayn-smoke: daydzhest → pravila → r6-daydzhest
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytyy #1) Ashbi — ustoychivaya degradatsiya (katbek); (Skrytyy #2) Cover&Thomas - umenshenie izbytochnosti.
# Earthly paragraph: a single button for local verification of the Republic of Belarus. The output is digest_*_rb.(zhsion|md).
# c=a+b

set -euo pipefail
python tests/r6_smoke.py || true
echo "[R6] Gotovo."
