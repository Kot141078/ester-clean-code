#!/usr/bin/env bash
set -euo pipefail

ART="artifacts/perf"
P95="${ESTER_P95_MS:-2000}"
P99="${ESTER_P99_MS:-5000}"
FAIL="${ESTER_FAIL_RATE:-0.01}"

if ! compgen -G "$ART/*.summary.json" > /dev/null; then
  echo "[perf-ci] net $ART/*.summary.json — snachala progonite profili (make perf-all)" >&2
  exit 2
fi

python3 - <<PY
import os, json, glob, sys
ART="${ART}"
P95=float(os.getenv("ESTER_P95_MS","${P95}"))
P99=float(os.getenv("ESTER_P99_MS","${P99}"))
FAIL=float(os.getenv("ESTER_FAIL_RATE","${FAIL}"))

bad=[]
for p in sorted(glob.glob(os.path.join(ART, "*.summary.json"))):
    with open(p, "r", encoding="utf-8") as f:
        data=json.load(f)
    m=data.get("metrics",{})
    dur=(m.get("http_req_duration",{}) or {}).get("values",{}) or {}
    fail=(m.get("http_req_failed",{}) or {}).get("values",{}) or {}
    p95=float(dur.get("p(95)", P95))
    p99=float(dur.get("p(99)", P99))
    rate=float(fail.get("rate", 0.0))
    if p95>P95 or p99>P99 or rate>FAIL:
        bad.append((os.path.basename(p), p95, p99, rate))

if bad:
    for name,p95,p99,rate in bad:
        print(f"[perf-ci] FAIL: {name}: p95={p95:.1f}ms p99={p99:.1f}ms fail_rate={rate:.4f}")
    sys.exit(1)
else:
    print("[perf-ci] OK: vse porogi vyderzhany")
PY
