#!/usr/bin/env bash
set -euo pipefail

CMD="${1:-status}"
IFACE="${IFACE:-eth0}"
DELAY_MS="${DELAY_MS:-150}"
JITTER_MS="${JITTER_MS:-30}"
LOSS_PCT="${LOSS_PCT:-0}"

netem_args() {
  local args=()
  [ "${DELAY_MS}" != "0" ] && args+=(delay "${DELAY_MS}ms" "${JITTER_MS}ms" distribution normal)
  [ "${LOSS_PCT}" != "0" ] && args+=(loss "${LOSS_PCT}%")
  echo "${args[@]}"
}

case "$CMD" in
  start)
    if tc qdisc show dev "$IFACE" | grep -q "netem"; then
      echo "[netem] uzhe aktiven na ${IFACE}"; exit 0; fi
    ARGS="$(netem_args)"
    if [ -z "$ARGS" ]; then
      echo "[netem] net parametrov (delay/loss) — nichego ne delaem"; exit 0; fi
    tc qdisc add dev "$IFACE" root netem $ARGS
    echo "[netem] vklyuchen na ${IFACE}: $ARGS"
    ;;
  stop)
    if tc qdisc show dev "$IFACE" | grep -q "netem"; then
      tc qdisc del dev "$IFACE" root netem
      echo "[netem] vyklyuchen na ${IFACE}"
    else
      echo "[netem] nichego ne bylo vklyucheno na ${IFACE}"
    fi
    ;;
  status)
    tc qdisc show dev "$IFACE" || true
    ;;
  *)
    echo "usage: IFACE=eth0 [DELAY_MS=150] [JITTER_MS=30] [LOSS_PCT=1] $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
