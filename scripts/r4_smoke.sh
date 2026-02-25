#!/usr/bin/env bash
# RF/skripts/rch_stoke.sh - RF smoke wrapper for *them
# Bridges: (Explicit) Enderton - verifiable predicates; (Hidden #1) Ashby - resilience; (Hidden #2) Carpet & Thomas - minimal information.
# Zemnoy abzats: probuet rerank+summary s LM Studio, pri nedostupnosti — ne padaet (fallback).
# c=a+b

set -euo pipefail
python tests/r4_smoke.py || true
echo "[R4] Gotovo."
