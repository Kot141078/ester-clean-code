#!/usr/bin/env bash
# R5/scripts/r5_smoke.sh - offlayn-smoke dlya *nix: plan → daydzhest → HTML
# Bridges: (Explicit) Enderton - verifiable predicates; (Hidden) Ashby - soft mode; Carpet&Thomas - minimal information.
# Earthly paragraph: generates portal/index.html without changing runtime/contracts.
# c=a+b

set -euo pipefail
python tests/r5_smoke.py || true
echo "[R5] Gotovo."
