#!/usr/bin/env bash
set -euo pipefail
VER="${1:-$(date +%Y.%m.%d-%H%M)}"
OUT="ester-${VER}.zip"

rm -rf release && mkdir -p release/{config,docs,presets}
cp -v release_templates/install_ester_pro.sh release/ || true
cp -v release_templates/docker-compose.prod.yml release/ || true
cp -v presets/*.yaml release/presets/ || true
cp -v docs/PRICING.md release/docs/ || true
cp -v release_templates/.env.example release/config/ || true
echo "${VER}" > release/VERSION

( cd release && zip -r "../${OUT}" . )
echo "Created ${OUT}"
