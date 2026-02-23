#!/usr/bin/env bash
set -euo pipefail
ENV_FILE="${1:-.env}"
backup="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$ENV_FILE" "$backup"
new_jwt=$(openssl rand -hex 32)
new_csrf=$(openssl rand -hex 32)
new_key=$(python3 - <<'PY'
import os,base64
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
)
sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$new_jwt/" "$ENV_FILE" || echo "JWT_SECRET=$new_jwt" >> "$ENV_FILE"
sed -i "s/^CSRF_SECRET=.*/CSRF_SECRET=$new_csrf/" "$ENV_FILE" || echo "CSRF_SECRET=$new_csrf" >> "$ENV_FILE"
sed -i "s/^ENCRYPTION_MASTER_KEY_BASE64=.*/ENCRYPTION_MASTER_KEY_BASE64=$new_key/" "$ENV_FILE" || echo "ENCRYPTION_MASTER_KEY_BASE64=$new_key" >> "$ENV_FILE"
echo "[rotate] done. backup: $backup"
