#!/usr/bin/env bash
set -euo pipefail

ART="artifacts/recovery"
mkdir -p "$ART"
OUT="$ART/log_snapshot.txt"
LINES="${LOG_TAIL_LINES:-5000}"
UNIT="${LOG_UNIT:-ester-web.service}"
LOG_PATH="${LOG_PATH:-}"

{
  echo "=== LOG SNAPSHOT ==="
  echo "time: $(date -Iseconds)"
  echo "lines: $LINES"
  echo "unit: $UNIT"
  echo "log_path: ${LOG_PATH:-<none>}"
  echo

  if command -v journalctl >/dev/null 2>&1; then
    echo "== journalctl -u $UNIT -n $LINES =="
    journalctl -u "$UNIT" -n "$LINES" --no-pager || echo "(journalctl failed)"
  elif [ -n "$LOG_PATH" ] && [ -r "$LOG_PATH" ]; then
    echo "== tail -n $LINES $LOG_PATH =="
    tail -n "$LINES" "$LOG_PATH" || echo "(tail failed)"
  else
    echo "(no journald, no LOG_PATH — nothing to snapshot)"
  fi
} >"$OUT"

echo "[log-snapshot] wrote $OUT"
