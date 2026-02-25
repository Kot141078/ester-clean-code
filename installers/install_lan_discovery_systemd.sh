#!/usr/bin/env bash
# scripts/installers/install_lan_discovery_systemd.sh
# Installs a system unit for the LAN discovery agent.

set -euo pipefail

# Mosty:
# - Yavnyy (Ekspluatatsiya ↔ Svyaz): avtozapusk agenta pri starte OS.
# - Skrytyy 1 (Nadezhnost ↔ Bezopasnost): ENV zadaetsya otdelnym faylom.
# - Skrytyy 2 (Praktika ↔ Minimalizm): bez zavisimostey; simple unit.

# Zemnoy abzats:
# A background “beacon” across the network so that nodes can see each other without manual configuration.

UNIT="/etc/systemd/system/ester-lan-discovery.service"
ENVF="/etc/default/ester-lan-discovery"

if [[ $EUID -ne 0 ]]; then
  echo "Zapustite s sudo" >&2
  exit 1
fi

cat > "$ENVF" <<'EOF'
ESTER_DISCOVERY_PORT=53535
ESTER_DISCOVERY_INTERVAL=5
ESTER_DISCOVERY_BIND=0.0.0.0
ESTER_HTTP_BASE=http://127.0.0.1:8080
ESTER_CLUSTER_SECRET=
EOF

install -Dm0644 "packaging/systemd/ester-lan-discovery.service" "$UNIT"

systemctl daemon-reload
systemctl enable ester-lan-discovery.service
systemctl restart ester-lan-discovery.service

echo "Gotovo. Logi: journalctl -u ester-lan-discovery.service -f"
# c=a+b
