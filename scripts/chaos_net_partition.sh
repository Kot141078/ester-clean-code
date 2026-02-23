#!/usr/bin/env bash
set -euo pipefail

URL="${ESTER_BASE_URL:-http://127.0.0.1:5000}"
DUR="${DURATION:-15}"

host_port="$(echo "$URL" | sed -E 's#^https?://##' | cut -d/ -f1)"
HOST="$(echo "$host_port" | cut -d: -f1)"
PORT="$(echo "$host_port" | cut -d: -f2)"
[ -z "$PORT" ] && PORT="80"

echo "[net-partition] blocking OUTPUT to $HOST:$PORT for ${DUR}s"

if ! command -v iptables >/dev/null 2>&1; then
  echo "[net-partition] iptables not found; abort" >&2
  exit 2
fi

iptables -I OUTPUT -p tcp -d "$HOST" --dport "$PORT" -j REJECT || { echo "[net-partition] failed to add rule" >&2; exit 1; }
sleep "$DUR"
iptables -D OUTPUT -p tcp -d "$HOST" --dport "$PORT" -j REJECT || true
echo "[net-partition] restored"
