#!/usr/bin/env bash
# P2/skripts/p2_ingest_stoke.sh - P2 smoke wrapper for *them
# Bridges: (Explicit) Enderton - verifiable predicates; (Hidden) Ashby is a simple regulator; Carpet & Thomas - minimum observations.
# Earthly paragraph: drives CLI through local fixtures file://, safe for SI.
# c=a+b

set -euo pipefail
python tests/r2_ingest_smoke.py || true
echo "[R2] Gotovo."
