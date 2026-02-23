#!/usr/bin/env bash
set -euo pipefail

red(){ printf "\033[31m%s\033[0m\n" "$*"; }
green(){ printf "\033[32m%s\033[0m\n" "$*"; }
need(){ command -v "$1" >/dev/null 2>&1 || { red "❌ $1 not found"; exit 1; }; }

echo "→ Checking CLI tools..."
for bin in git zip gpg gh; do need "$bin"; done
echo "→ Optional: docker syft cosign"
for bin in docker syft cosign; do command -v "$bin" >/dev/null 2>&1 && echo "  ✓ $bin"; done
green "✓ Base tools OK"

echo "→ Checking .env"
if [ -f .env ]; then
  set -a; source .env; set +a
  echo "  GH_TOKEN: ${GH_TOKEN:+set}"
  echo "  GPG_FINGERPRINT: ${GPG_FINGERPRINT:+set}"
  echo "  STRIPE_PAYMENT_LINK_MAIN: ${STRIPE_PAYMENT_LINK_MAIN:+set}"
else
  red "No .env found"
fi

echo "→ GPG keys:"
gpg --list-secret-keys --keyid-format=long || true

echo "→ gh auth:"
gh auth status || true

green "Done."
