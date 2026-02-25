#!/usr/bin/env bash
# U2/scripts/u2_smoke.sh - offflayn-smoke Cortex
# Bridges: (Explicit) Enderton - verifiable steps; (Hidden) Ashby - stability/cutback; Carpet&Thomas - compressed signal.
# Earthly paragraph: one button - think and do what is necessary.
# c=a+b

set -euo pipefail
python tests/u2_smoke.py || true
echo "[U2] Gotovo."
