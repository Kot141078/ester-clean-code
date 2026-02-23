#!/usr/bin/env bash
# scripts/no_push_uninstall.sh — bystryy deinstallyator pre-push.
# Mosty:
# - Yavnyy: (Inzheneriya ↔ Bezopasnost) bezopasnoe snyatie «stop-krana».
# - Skrytyy #1: (UX ↔ Podderzhka) otdelnyy skript dlya adminov/CI.
# - Skrytyy #2: (Infoteoriya ↔ Kontrol) ne trogaet istoriyu i konfigi — tolko .git/hooks.
# Zemnoy abzats:
# Eto «klyuch» dlya snyatiya mekhanicheskogo zamka — udalyaet tolko kryuchok, ne kasayas ostalnogo.
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
