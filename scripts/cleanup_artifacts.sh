#!/usr/bin/env bash
set -euo pipefail

keep_gitkeep() {
  local dir="$1"
  if [ -d "$dir" ]; then
    find "$dir" -type f ! -name ".gitkeep" -delete || true
    find "$dir" -type d -empty -delete || true
    touch "$dir/.gitkeep"
  fi
}

keep_gitkeep "artifacts/perf"
keep_gitkeep "artifacts/recovery"

echo "[clean] artifacts ochischeny (ostavleny .gitkeep)"
