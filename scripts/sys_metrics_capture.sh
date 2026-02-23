#!/usr/bin/env bash
set -euo pipefail

ART="artifacts/perf"
mkdir -p "$ART"

ts() { date +%Y-%m-%dT%H:%M:%S%z; }

OUT_SYS="$ART/sys_overview.log"
OUT_CPU="$ART/sys_cpu_vmstat.log"
OUT_IO="$ART/sys_io_iostat.log"
OUT_MEM="$ART/sys_mem_free.log"
OUT_DF="$ART/sys_disk_df.log"
OUT_NETSTAT="$ART/sys_netstat.log"
OUT_SS="$ART/sys_ss.log"
OUT_TOP="$ART/sys_top.log"
OUT_PS="$ART/sys_ps_ester.log"

{
  echo "=== System overview ($(ts)) ==="
  uname -a || true
  echo
  echo "== /etc/os-release =="
  [ -f /etc/os-release ] && cat /etc/os-release || true
} >"$OUT_SYS"

{
  echo "=== vmstat 1 5 ==="
  if command -v vmstat >/dev/null 2>&1; then vmstat 1 5; else echo "vmstat not found"; fi
} >"$OUT_CPU"

{
  echo "=== iostat -x 1 5 ==="
  if command -v iostat >/dev/null 2>&1; then iostat -x 1 5; else echo "iostat not found (install sysstat)"; fi
} >"$OUT_IO"

{
  echo "=== free -h ==="
  if command -v free >/dev/null 2>&1; then free -h; else echo "free not found"; fi
} >"$OUT_MEM"

{
  echo "=== df -hT ==="
  df -hT || true
} >"$OUT_DF"

{
  echo "=== netstat -s (or ss) ==="
  if command -v netstat >/dev/null 2>&1; then netstat -s; else echo "netstat not found"; fi
} >"$OUT_NETSTAT"

{
  echo "=== ss -s ==="
  if command -v ss >/dev/null 2>&1; then ss -s; else echo "ss not found"; fi
} >"$OUT_SS"

{
  echo "=== top -b -n 1 | head -n 100 ==="
  if command -v top >/dev/null 2>&1; then top -b -n 1 | head -n 200; else echo "top not found"; fi
} >"$OUT_TOP"

{
  echo "=== ps aux | grep -i 'ester\|python' ==="
  ps aux | grep -Ei 'ester|python|gunicorn|uvicorn' | grep -v grep || true
} >"$OUT_PS"

echo "[sys-metrics] saved:"
ls -la "$ART"/sys_*.log || true
