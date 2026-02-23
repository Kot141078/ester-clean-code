#!/usr/bin/env bash
set -euo pipefail
BRANCH="chore/legal-and-ignore"
PATCH_FILE="${1:-pr_legal_and_ignore.patch}"

# Ensure git repo
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Run inside your repo"; exit 1; }

git checkout -b "$BRANCH" || git checkout "$BRANCH"

# Apply patch
git apply --whitespace=fix "$PATCH_FILE"

# Commit (with DCO signoff optional)
git add .gitignore LICENSE-CE LICENSE-COMMERCIAL TRADEMARKS.md NOTICE CONTRIBUTING.md DCO THIRD-PARTY-LICENSES
git commit -s -m "chore(legal): add CE & commercial licenses, TM policy, NOTICE, CONTRIBUTING, DCO, third-party licenses, and .gitignore"

# Push
git push -u origin "$BRANCH"

# Create PR if gh is available
if command -v gh >/dev/null 2>&1; then
  gh pr create --fill --title "chore(legal): add licenses & .gitignore" --body "Adds legal pack and .gitignore (data/secrets excluded)."
else
  echo "Install GitHub CLI (gh) to auto-create a PR, or open one via the web UI."
fi
