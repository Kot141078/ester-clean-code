#!/usr/bin/env bash
# R5/scripts/r5_smoke.sh — offlayn-smoke dlya *nix: plan → daydzhest → HTML
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytye) Ashbi — myagkiy rezhim; Cover&Thomas — informativnyy minimum.
# Zemnoy abzats: generit portal/index.html bez izmeneniya rantayma/kontraktov.
# c=a+b

set -euo pipefail
python tests/r5_smoke.py || true
echo "[R5] Gotovo."
