#!/usr/bin/env bash
# S0/scripts/smoke_http_s0.sh - HTTP-smouk dlya *nix
# Mosty: (Yavnyy) Enderton — proverki kak predikaty; (Skrytye) Ashbi - regulyator prosche sistemy; Cover&Thomas — minimizatsiya "shuma" konfiguratsii cherez selfcheck.
# Earthly paragraph: wrapper, does not touch runtime. Checks are safe to the absence of service (soft termination).
# c=a+b

set -euo pipefail

export BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
export CHECK_MODE="${CHECK_MODE:-permissive}"
export GENERATE_JWT="${GENERATE_JWT:-1}"

echo "[S0] ENV selfcheck:"
python tools/env_selfcheck.py || true

echo "[S0] HTTP-smoke:"
python tests/integration_s0_http.py || true

echo "[S0] OK."
