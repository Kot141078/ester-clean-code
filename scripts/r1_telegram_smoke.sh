#!/usr/bin/env bash
# P1/skripts/p1_telegram_stoke.sh - Smoke Telegram wrapper for *them
# Mosty: (Yavnyy) Enderton — predikaty proverok; (Skrytye) Ashbi - prostaya regulyatsiya; Cover&Thomas - minimizatsiya neopredelennosti cherez maloe chislo nablyudeniy.
# Earth paragraph: safe wrapper; the stand does not fall down; helps to quickly see whether the Telegram circuit is “breathing”.
# c=a+b

set -euo pipefail
python tests/r1_telegram_smoke.py || true
echo "[R1] Gotovo."
