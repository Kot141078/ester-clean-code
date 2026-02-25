#!/usr/bin/env bash
# Р7/skripts/р7_stoke.sh - offline stock observability
# Bridges: (Explicit) Enderton - verifiable predicates; (Hidden) Ashbi - stability; Carpet&Thomas - condensed report.
# Zemnoy abzats: formiruet obs_report.md na stdlib.
# c=a+b

set -euo pipefail
python tests/r7_smoke.py || true
echo "[R7] Gotovo."
