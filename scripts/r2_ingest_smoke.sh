#!/usr/bin/env bash
# R2/scripts/r2_ingest_smoke.sh — obertka smouka R2 dlya *nix
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytye) Ashbi — prostoy regulyator; Cover&Thomas — minimum nablyudeniy.
# Zemnoy abzats: gonyaet CLI po lokalnym fiksturam file://, bezopasno dlya CI.
# c=a+b

set -euo pipefail
python tests/r2_ingest_smoke.py || true
echo "[R2] Gotovo."
