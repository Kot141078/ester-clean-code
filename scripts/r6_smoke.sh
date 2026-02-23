#!/usr/bin/env bash
# R6/scripts/r6_smoke.sh — offlayn-smoke: daydzhest → pravila → r6-daydzhest
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytyy #1) Ashbi — ustoychivaya degradatsiya (katbek); (Skrytyy #2) Cover&Thomas — umenshenie izbytochnosti.
# Zemnoy abzats: edinaya knopka dlya lokalnoy proverki R6. Na vykhode digest_*_r6.(json|md).
# c=a+b

set -euo pipefail
python tests/r6_smoke.py || true
echo "[R6] Gotovo."
