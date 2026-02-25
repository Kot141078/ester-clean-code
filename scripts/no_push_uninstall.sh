#!/usr/bin/env bash
# skripts/no_push_uninstall.sh - quick pre-push uninstaller.
# Mosty:
# - Yavnyy: (Inzheneriya ↔ Bezopasnost) bezopasnoe snyatie “stop-krana”.
# - Hidden #1: (UX support) separate script for admins/CI.
# - Skrytyy #2: (Infoteoriya ↔ Kontrol) ne trogaet istoriyu i configi - tolko .git/hooks.
# Zemnoy abzats:
# This is a “key” for removing a mechanical lock - it removes only the hook, without touching the rest.
# c=a+b

set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$(pwd)")"
HOOK_DST="$REPO_ROOT/.git/hooks/pre-push"

if [[ -f "$HOOK_DST" ]]; then
  rm -f "$HOOK_DST"
  echo "pre-push removed: $HOOK_DST"
else
  echo "pre-push not installed: $HOOK_DST"
fi
