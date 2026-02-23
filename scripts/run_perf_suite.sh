#!/usr/bin/env bash
set -euo pipefail

echo "[suite] bench (read/replicate)"; bash scripts/bench_k6.sh
echo "[suite] bench-ops"; bash scripts/bench_k6_ops.sh
echo "[suite] bench-ingest"; bash scripts/bench_k6_ingest.sh
echo "[suite] bench-rag"; bash scripts/bench_k6_rag.sh
echo "[suite] aggregate"; python3 scripts/perf_aggregate.py
echo "[suite] ci gate (pytest thresholds)"; ESTER_PERF_VERIFY=1 pytest -q tests/perf/test_perf_thresholds.py
echo "[suite] alt gate (script)"; bash scripts/perf_ci_gate.sh
echo "[suite] OK — vse profili i geyty proydeny"
