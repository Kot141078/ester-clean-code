#!/usr/bin/env bash
# С0/skripts/gen_zhvt_secret.sh - a convenient secret generation wrapper for *them
# Bridges: (Explicit) Enderton - testability of conditions; (Hidden) Ashby is a simple regulator; Janes is a priori of safety.
# Earthly paragraph: we write in .env only by flag; safe for SI/LAN.
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
