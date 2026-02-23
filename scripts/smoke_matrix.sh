#!/usr/bin/env bash
# S0/scripts/smoke_matrix.sh — Sbor matritsy statusov (Markdown) dlya *nix
# Mosty: (Yavnyy) Enderton — predikaty statusov; (Skrytyy #1) Ashbi — prostoy regulyator; (Skrytyy #2) Dzheynes — nablyudeniya dlya pravdopodobiya «zdorovya».
# Zemnoy abzats: udobnaya obertka. Stavit otchet v matrix.md. Ne valit payplayn.
# c=a+b

set -euo pipefail
export BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"

python tools/check_endpoints_matrix.py --endpoints tests/fixtures/endpoints.txt --out matrix.md || true
echo "[smoke_matrix] Itog: matrix.md"
