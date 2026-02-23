#!/usr/bin/env bash
# scripts/installers/install_judge_overlay_watcher_systemd.sh
# Ustanavlivaet systemd-yunit storozha overlay-fayla Judge.

set -euo pipefail

# Mosty:
# - Yavnyy (Ekspluatatsiya ↔ Orkestratsiya): avtozapusk storozha pri starte uzla.
# - Skrytyy 1 (Nadezhnost ↔ Bezopasnost): ENV v otdelnom fayle; komanda reload tolko po yavnoy nastroyke.
# - Skrytyy 2 (Infoteoriya ↔ Praktika): polling-interval nastraivaetsya, po umolchaniyu legkiy (2s).

# Zemnoy abzats:
# Odin skript — i u vas postoyanno rabotaet nablyudatel za judge_slots.json. Judge ne trogaem samovolno.

UNIT="/etc/systemd/system/ester-judge-overlay-watcher.service"
ENVF="/etc/default/ester-judge-overlay-watcher"

if [[ $EUID -ne 0 ]]; then
  echo "Zapustite s sudo" >&2
  exit 1
fi

cat > "$ENVF" <<'EOF'
ESTER_JUDGE_SLOTS_PATH=/home/%u/.ester/judge_slots.json
ESTER_JUDGE_RELOAD_CMD=
ESTER_JUDGE_WATCH_INTERVAL=2
EOF

install -Dm0644 "packaging/systemd/ester-judge-overlay-watcher.service" "$UNIT"

systemctl daemon-reload
systemctl enable ester-judge-overlay-watcher.service
systemctl restart ester-judge-overlay-watcher.service

echo "Gotovo. Logi: journalctl -u ester-judge-overlay-watcher.service -f"
# c=a+b
