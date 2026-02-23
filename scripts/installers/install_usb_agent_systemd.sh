#!/usr/bin/env bash
# scripts/installers/install_usb_agent_systemd.sh
# Ustanavlivaet systemd-yunit dlya listeners.usb_one_question_agent.

set -euo pipefail

# Mosty:
# - Yavnyy (Inzheneriya ↔ Ekspluatatsiya): odin skript — gotovaya sluzhba.
# - Skrytyy 1 (Nadezhnost ↔ Bezopasnost): yunit v /etc/systemd/system, ENV v otdelnom fayle.
# - Skrytyy 2 (Praktika ↔ Avtonomiya): avtozapusk pri starte OS i restart po sboyu.

# Zemnoy abzats:
# Zapusk agenta kak demona systemd — samyy nadezhnyy sposob v Linux: perezapusk, logirovanie, targety.

UNIT_PATH="/etc/systemd/system/ester-usb-agent.service"
ENV_PATH="/etc/default/ester-usb-agent"

if [[ $EUID -ne 0 ]]; then
  echo "Zapustite s sudo" >&2
  exit 1
fi

# Pishem ENV (mozhno pravit rukami pozzhe)
cat > "$ENV_PATH" <<'EOF'
# ENV dlya Ester USB Agent
ESTER_ZT_AUTO_ACCEPT_SECONDS=10
ESTER_ZT_POLL_INTERVAL=5
AB_MODE=A
# Mozhno ukazat arkhiv/damp po umolchaniyu:
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
