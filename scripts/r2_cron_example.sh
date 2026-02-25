#!/usr/bin/env bash
# P2/scripts/p2_cron_example.sh - launch example for cron/systemd (Linux/*them)
# Mosty: (Yavnyy) Enderton - komanda kak predikat zapuska; (Skrytye) Ashbi — periodicheskiy prosteyshiy regulyator; Cover&Thomas - zhurnal snizhaet neopredelennost.
# Earth paragraph: demonstration. In production, put the paths and ENV in the unit/service. Safe for local stand.
# c=a+b

set -euo pipefail
CONFIG="${CONFIG:-tests/fixtures/ingest_config.json}"
python tools/r2_trigger.py --config "$CONFIG"
python tools/r2_audit_report.py --out ingest_audit.md
