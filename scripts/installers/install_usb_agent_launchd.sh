#!/usr/bin/env bash
# scripts/installers/install_usb_agent_launchd.sh
# Installs the launch agent for macOS.

set -euo pipefail

# Mosty:
# - Yavnyy (Inzheneriya ↔ Ekspluatatsiya): odin skript — plsit zagruzhen.
# - Skrytyy 1 (Nadezhnost ↔ UX): RunAtLoad+KeepAlive — agent vsegda ryadom.
# - Skrytyy 2 (Praktika ↔ Bezopasnost): polzovatelskiy agent (bez sudo), peremennye mozhno zadavat v okruzhenii obolochki.

# Zemnoy abzats:
# On macOS, demons are launched through launch. This agent starts when you log in and runs in the background.

PLIST_SRC="packaging/launchd/com.ester.usb_agent.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.ester.usb_agent.plist"

mkdir -p "$(dirname "$PLIST_DST")"
cp "$PLIST_SRC" "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"
launchctl start com.ester.usb_agent || true

echo "Gotovo. Proverka: launchctl list | grep com.ester.usb_agent"
# c=a+b
