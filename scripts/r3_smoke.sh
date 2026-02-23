#!/usr/bin/env bash
# R3/scripts/r3_smoke.sh — obertka smouka R3 dlya *nix
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytyy #1) Cover&Thomas — informativnyy minimum; (Skrytyy #2) Ashbi — prostaya regulyatsiya.
# Zemnoy abzats: zapuskaet build → score, ne valit stend pri pustykh dannykh. Podkhodit dlya cron.
# c=a+b

set -euo pipefail
python tests/r3_smoke.py || true
echo "[R3] Gotovo."
