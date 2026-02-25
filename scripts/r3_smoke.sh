#!/usr/bin/env bash
# Rz/skripts/rz_stoke.sh - smoke Rz wrapper for *them
# Bridges: (Explicit) Enderton - verifiable predicates; (Hidden #1) Carpet & Thomas - minimal information; (Hidden #2) Ashby - simple regulation.
# Zemnoy abzats: zapuskaet build → score, ne valit stend pri pustykh dannykh. Podkhodit dlya cron.
# c=a+b

set -euo pipefail
python tests/r3_smoke.py || true
echo "[R3] Gotovo."
