#!/usr/bin/env bash
# skripts/no_push_guard.sh - installation/control of a local pre-push “stop tap”.
# Mosty:
# - Yavnyy: (Inzheneriya ↔ Bezopasnost) lokalnyy khuk garantiruet, chto push ne uydet sluchayno.
# - Skrytyy #1: (Kibernetika ↔ Volya) flag .nopush i ENV ALLOW_PUSH — yavnye rychagi dlya vremennogo razresheniya.
# - Skrytyy #2: (UX ↔ Prozrachnost) status/doctor obyasnyayut tekuschee sostoyanie.
# Zemnoy abzats:
# This is a “mechanical lock” on the lever: by default it does not allow you to engage the gear (push) until you explicitly remove the latch.
# c=a+b

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$(pwd)")"
HOOK_SRC="$REPO_ROOT/tools/no_push/pre-push"
HOOK_DST="$REPO_ROOT/.git/hooks/pre-push"
FLAG_NOPUSH="$REPO_ROOT/.nopush"

green(){ printf "\033[32m%s\033[0m\n" "$*"; }
red(){ printf "\033[31m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }

cmd="${1:-}"

install_hook() {
  mkdir -p "$(dirname "$HOOK_DST")"
  if [[ ! -f "$HOOK_SRC" ]]; then
    red "Hook template not found: $HOOK_SRC"
    exit 1
  fi
  cp -f "$HOOK_SRC" "$HOOK_DST"
  chmod +x "$HOOK_DST"
  # enables default prohibition (flag file)
  if [[ ! -f "$FLAG_NOPUSH" ]]; then
    : > "$FLAG_NOPUSH"
  fi
  green "pre-push installed at $HOOK_DST"
  yellow "Push is DISABLED by default (flag .nopush present). Use ALLOW_PUSH=1 to override one-time."
}

uninstall_hook() {
  if [[ -f "$HOOK_DST" ]]; then
    rm -f "$HOOK_DST"
    green "pre-push removed"
  else
    yellow "pre-push not installed"
  fi
}

enable_block() {
  : > "$FLAG_NOPUSH"
  green "Push block ENABLED (.nopush created)"
}

disable_block() {
  rm -f "$FLAG_NOPUSH" || true
  green "Push block DISABLED (.nopush removed)"
  yellow "Remember: if ALLOW_PUSH=0 and .nopush absent, pushes still require manual ALLOW_PUSH=1 for one-time override."
}

status() {
  echo "repo: $REPO_ROOT"
  if [[ -f "$HOOK_DST" ]]; then
    echo "hook: installed -> $HOOK_DST"
  else
    echo "hook: NOT installed"
  fi
  if [[ -f "$FLAG_NOPUSH" ]]; then
    echo "nopush flag: PRESENT (.nopush) → pushes are blocked unless ALLOW_PUSH=1"
  else
    echo "nopush flag: absent → pushes require ALLOW_PUSH=1 (one-time)"
  fi
}

doctor() {
  status
  if [[ -f "$HOOK_DST" ]]; then
    if grep -q "NoPush guard" "$HOOK_DST"; then
      green "hook check: looks good"
    else
      red "hook check: unexpected content (not NoPush guard?)"
    fi
  fi
  # dry-run simulation hint
  echo "Try: git push --dry-run (expect failure unless ALLOW_PUSH=1)"
}

case "$cmd" in
  install) install_hook ;;
  uninstall) uninstall_hook ;;
  enable) enable_block ;;
  disable) disable_block ;;
  status) status ;;
  doctor) doctor ;;
  *)
    cat <<USAGE
Usage: $0 <command>
  install    — ustanovit pre-push i sozdat .nopush
  uninstall  — udalit pre-push
  enable     — vklyuchit zapret (sozdat .nopush)
  disable    — snyat zapret (udalit .nopush)
  status     — pokazat sostoyanie
  doctor     — diagnostika
USAGE
    ;;
esac
