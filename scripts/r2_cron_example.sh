#!/usr/bin/env bash
# R2/scripts/r2_cron_example.sh — primer zapuska dlya cron/systemd (Linux/*nix)
# Mosty: (Yavnyy) Enderton — komanda kak predikat zapuska; (Skrytye) Ashbi — periodicheskiy prosteyshiy regulyator; Cover&Thomas — zhurnal snizhaet neopredelennost.
# Zemnoy abzats: demonstratsiya. V prode vynesi puti i ENV v unit/service. Bezopasno dlya lokalnogo stenda.
# c=a+b

set -euo pipefail
CONFIG="${CONFIG:-tests/fixtures/ingest_config.json}"
python tools/r2_trigger.py --config "$CONFIG"
python tools/r2_audit_report.py --out ingest_audit.md
