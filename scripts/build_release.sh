#!/usr/bin/env bash
# Reliznyy skript: bump versii, kommit, teg, push.
# Ispolzovanie:
#   ./scripts/build_release.sh [major|minor|patch] [-f]
# Po umolchaniyu: patch. Klyuch -f — ignorirovat gryaznoe derevo (ostorozhno).
set -euo pipefail

KIND="${1:-patch}"
FORCE="${2:-}"

if ! command -v git >/dev/null 2>&1; then
  echo "[release] git ne nayden" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if [[ "$FORCE" != "-f" ]]; then
  if ! git diff-index --quiet HEAD --; then
    echo "[release] Derevo ne chistoe. Zakommitte izmeneniya ili zapustite s -f" >&2
    exit 2
  fi
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[release] python3 ne nayden" >&2
  exit 2
fi

# 1) bump VERSION
NEW_VER="$(python3 scripts/version_bump.py "$KIND")"
TAG="v${NEW_VER}"

# 2) commit VERSION (esli izmenilsya)
if ! git diff --quiet -- VERSION; then
  git add VERSION
  git commit -m "chore(release): ${TAG}"
fi

# 3) proverim, chto tega esche net
if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "[release] Teg $TAG uzhe suschestvuet" >&2
  exit 2
fi

# 4) sozdaem teg i pushim
git tag -a "$TAG" -m "$TAG"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push origin "$CURRENT_BRANCH"
git push origin "$TAG"

echo "[release] Gotovo: $TAG"
echo "[release] V GitHub Actions srabotaet workflow release.yml: sborka obraza, SBOM, podpis, reliz."
