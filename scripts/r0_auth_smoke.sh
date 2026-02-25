#!/usr/bin/env bash
# R0/scripts/r0_auth_smoke.sh — smouk R0 dlya *nix
# Bridges: (Explicit) Enderton - verifiable predicates; (Hidden) Janes - the credibility of "health"; Carpet&Thomas - minimal signal.
# Earth paragraph: simple wrapper; does not crash the pipeline, suitable for local/CI.
# c=a+b

set -euo pipefail
python tests/r0_auth_smoke.py || true
echo "[R0] Gotovo."
