#!/usr/bin/env bash
set -euo pipefail

PROM_URL="${PROM_URL:-http://localhost:9090}"

echo "[prom-check] Using ${PROM_URL}"

# Proverim, chto API Prometheus otvechaet
if ! curl -fsS "${PROM_URL}/-/healthy" >/dev/null; then
  echo "[prom-check] ERROR: Prometheus not healthy"
  exit 1
fi

# Proverim, chto target ester viden i UP.
targets_json="$(curl -fsS "${PROM_URL}/api/v1/targets?state=active")"

# Probuem prostym sposobom bez jq
echo "${targets_json}" | grep -q '"health":"up"' || {
  echo "[prom-check] WARN: no active target with health=up found (raw check)."
}

# Proverim metriku up{job="ester"} cherez query
q="$(python3 - <<'PY'
import os, sys, urllib.parse, urllib.request, json
prom = os.environ.get("PROM_URL","http://localhost:9090")
query = 'up{job="ester"}'
url = f"{prom}/api/v1/query?query=" + urllib.parse.quote(query)
with urllib.request.urlopen(url, timeout=5) as r:
    data = json.load(r)
if data.get("status") != "success":
    print("FAIL")
    sys.exit(2)
result = data.get("data",{}).get("result",[])
if not result:
    print("EMPTY")
    sys.exit(3)
vals = [float(s.get('value',[0,0])[1]) for s in result]
print("OK" if any(v>0.5 for v in vals) else "DOWN")
PY
)"

case "$q" in
  OK)
    echo "[prom-check] OK: up{job="ester"} > 0"
    ;;
  DOWN)
    echo "[prom-check] ERROR: up{job="ester"} == 0"
    exit 4
    ;;
  EMPTY)
    echo "[prom-check] WARN: no series for up{job="ester"}"
    ;;
  FAIL)
    echo "[prom-check] ERROR: query failed"
    exit 5
    ;;
  *)
    echo "[prom-check] WARN: unexpected status: $q"
    ;;
esac

echo "[prom-check] Done."
