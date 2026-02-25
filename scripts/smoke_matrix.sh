#!/usr/bin/env bash
# С0/skripts/stoke_matrix.sh - Collection of status matrix (Markdovn) for *them
# Bridges: (Explicit) Enderton - status predicates; (Hidden #1) Ashby is a simple regulator; (Hidden #2) Janes - observations for the credibility of "health".
# Earthly paragraph: a convenient wrapper. Place a report in Matrix.md. The pipeline doesn't fail.
# c=a+b

set -euo pipefail
export BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"

python tools/check_endpoints_matrix.py --endpoints tests/fixtures/endpoints.txt --out matrix.md || true
echo "[smoke_matrix] Itog: matrix.md"
