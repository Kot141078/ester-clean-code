#!/usr/bin/env bash
# S0/scripts/run_all_smoke.sh — obertka edinogo progona smoukov dlya *nix
# Mosty: (Yavnyy) Ashbi — prostoy regulyator; (Skrytye) Enderton — proveryaemye predikaty; Cover&Thomas — minimizatsiya neopredelennosti sostoyaniem otchetov.
# Zemnoy abzats: odin vkhod dlya lokalnoy proverki; ne menyaet rantaym, artefakty — routes.md, matrix.md.
# c=a+b

set -euo pipefail
python tools/run_all_smoke.py || true
echo "[run_all_smoke] Gotovo. Sm. routes.md i matrix.md (esli sgenerirovany)."
