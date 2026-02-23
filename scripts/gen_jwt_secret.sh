#!/usr/bin/env bash
# S0/scripts/gen_jwt_secret.sh — udobnaya obertka generatsii sekreta dlya *nix
# Mosty: (Yavnyy) Enderton — proveryaemost usloviy; (Skrytye) Ashbi — prostoy regulyator; Dzheynes — apriory bezopasnosti.
# Zemnoy abzats: pishem v .env tolko po flagu; bezopasno dlya CI/lokalki.
# c=a+b

set -euo pipefail
LEN="${1:-64}"
MODE="${MODE:-base64url}"
DOTENV="${DOTENV:-}"

if [ -n "${DOTENV}" ]; then
  python tools/gen_jwt_secret.py --length "$LEN" --mode "$MODE" --write-dotenv "$DOTENV"
else
  python tools/gen_jwt_secret.py --length "$LEN" --mode "$MODE"
fi
