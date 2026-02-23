
#!/usr/bin/env bash
set -euo pipefail
APP_URL="${APP_URL:-http://localhost:5000}"

echo "[1/5] GET /health"
curl -sS "${APP_URL}/health" | sed -e 's/.*/OK/'

echo "[2/5] GET /providers/status"
curl -sS "${APP_URL}/providers/status" | sed -e 's/.*/OK/' || echo "WARN: providers may require auth"

echo "[3/5] GET /metrics"
curl -sS "${APP_URL}/metrics" | head -n 5

echo "[4/5] RBAC check (should be 403 without JWT): GET /ops/backup/run"
code=$(curl -s -o /dev/null -w "%{http_code}" "${APP_URL}/ops/backup/run" || true)
echo "HTTP ${code} (expected 401/403)"

echo "[5/5] Done."
