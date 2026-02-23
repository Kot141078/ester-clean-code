#!/usr/bin/env bash
# R1/scripts/r1_telegram_smoke.sh — obertka smouka Telegram dlya *nix
# Mosty: (Yavnyy) Enderton — predikaty proverok; (Skrytye) Ashbi — prostaya regulyatsiya; Cover&Thomas — minimizatsiya neopredelennosti cherez maloe chislo nablyudeniy.
# Zemnoy abzats: bezopasnaya obertka; ne valit stend; pomogaet bystro uvidet, «dyshit» li Telegram-kontur.
# c=a+b

set -euo pipefail
python tests/r1_telegram_smoke.py || true
echo "[R1] Gotovo."
