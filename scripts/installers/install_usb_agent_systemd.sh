#!/usr/bin/env bash
# scripts/installers/install_usb_agent_systemd.sh
# Installs the system unit for listeners.usb_one_question_agent.

set -euo pipefail

# Mosty:
# - Yavnyy (Inzheneriya ↔ Ekspluatatsiya): odin skript — gotovaya sluzhba.
# - Skrytyy 1 (Nadezhnost ↔ Bezopasnost): yunit v /etc/systemd/system, ENV v otdelnom fayle.
# - Skrytyy 2 (Praktika ↔ Avtonomiya): avtozapusk pri starte OS i restart po sboyu.

# Zemnoy abzats:
# Running an agent as a systemd daemon is the most reliable way in Linux: restarting, logging, targets.

UNIT_PATH="/etc/systemd/system/ester-usb-agent.service"
ENV_PATH="/etc/default/ester-usb-agent"

if [[ $EUID -ne 0 ]]; then
  echo "Zapustite s sudo" >&2
  exit 1
fi

# We write ENV (you can edit it manually later)
cat > "$ENV_PATH" <<'EOF'
# ENV for Esther USB Agent
ESTER_ZT_AUTO_ACCEPT_SECONDS=10
ESTER_ZT_POLL_INTERVAL=5
AB_MODE=A
# You can specify a default archive/dump:
# ESTER_USB_DEPLOY_ARCHIVE=/opt/ester/releases/CID.zip
# ESTER_USB_DEPLOY_DUMP=/opt/ester/dumps/ester_dump.tar.gz
EOF

# Kopiruem yunit
install -Dm0644 "packaging/systemd/ester-usb-agent.service" "$UNIT_PATH"

# Obnovim systemd i vklyuchim sluzhbu
systemctl daemon-reload
systemctl enable ester-usb-agent.service
systemctl restart ester-usb-agent.service

echo "Gotovo. Logi: journalctl -u ester-usb-agent.service -f"
# c=a+b
