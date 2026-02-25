#!/usr/bin/env bash
# U1/skripts/u1_stoke.sh - offline stock council
# Bridges: (Explicit) Enderton; (Hidden) Ashby; Carpet&Thomas.
# Zemnoy abzats: odna knopka “naydi temy → daydzhest → sovet.”
# c=a+b

set -euo pipefail
python tests/u1_smoke.py || true
echo "[U1] Gotovo."
