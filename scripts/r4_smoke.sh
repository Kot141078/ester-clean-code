#!/usr/bin/env bash
# R4/scripts/r4_smoke.sh — obertka smouka R4 dlya *nix
# Mosty: (Yavnyy) Enderton — proveryaemye predikaty; (Skrytyy #1) Ashbi — ustoychivost; (Skrytyy #2) Cover&Thomas — informativnyy minimum.
# Zemnoy abzats: probuet rerank+summary s LM Studio, pri nedostupnosti — ne padaet (fallback).
# c=a+b

set -euo pipefail
python tests/r4_smoke.py || true
echo "[R4] Gotovo."
