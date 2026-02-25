#!/usr/bin/env bash
# scripts/desktop/linux/ester_vdesk.sh
# Purpose: raise headless C (Hvfb) + window manager (flixbox) + VNS + noVNS
# and run the local RPA server (127.0.0.1:8732) from the user ester.

set -euo pipefail

USER_NAME="${USER_NAME:-ester}"
DISPLAY_NUM="${DISPLAY_NUM:-99}"
GEOM="${GEOM:-1920x1080x24}"
VNC_PORT="${VNC_PORT:-5901}"
NOVNC_PORT="${NOVNC_PORT:-6080}"
LOG_DIR="/var/log/ester"
RPA_BIN="/opt/ester/scripts/desktop/linux/ester_rpa.py"

id -u "${USER_NAME}" >/dev/null 2>&1 || sudo adduser --disabled-password --gecos "" "${USER_NAME}"

sudo -u "${USER_NAME}" mkdir -p "${LOG_DIR}"
mkdir -p /opt/ester/scripts/desktop/linux

export DISPLAY=":${DISPLAY_NUM}"

# Start Xvfb
if ! pgrep -f "Xvfb :${DISPLAY_NUM}" >/dev/null; then
  Xvfb ":${DISPLAY_NUM}" -screen 0 "${GEOM}" -nolisten tcp >>"${LOG_DIR}/xvfb.log" 2>&1 &
  sleep 0.7
fi

# Mini-okruzhenie: fluxbox
if ! pgrep -u "${USER_NAME}" -f "fluxbox" >/dev/null; then
  sudo -u "${USER_NAME}" bash -lc "fluxbox >>'${LOG_DIR}/fluxbox.log' 2>&1 &"
  sleep 0.5
fi

# VNC server
if ! pgrep -f "x11vnc -display :${DISPLAY_NUM}" >/dev/null; then
  x11vnc -display ":${DISPLAY_NUM}" -rfbport "${VNC_PORT}" -forever -nopw -shared >>"${LOG_DIR}/x11vnc.log" 2>&1 &
  sleep 0.5
fi

# noVNC shlyuz
if ! pgrep -f "websockify ${NOVNC_PORT}" >/dev/null; then
  websockify "${NOVNC_PORT}" "localhost:${VNC_PORT}" >>"${LOG_DIR}/novnc.log" 2>&1 &
  sleep 0.5
fi

# RPA server
if ! pgrep -f "${RPA_BIN}" >/dev/null; then
  /usr/bin/python3 "${RPA_BIN}" >>"${LOG_DIR}/rpa.log" 2>&1 &
fi

echo "VDesk up: VNC:${VNC_PORT}, noVNC:http://127.0.0.1:${NOVNC_PORT}, RPA:http://127.0.0.1:8732/health"
