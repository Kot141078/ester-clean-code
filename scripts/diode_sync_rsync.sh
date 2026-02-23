#!/usr/bin/env bash
# scripts/diode_sync_rsync.sh — odnostoronnyaya sinkhronizatsiya OUTBOX → INBOX dlya "data diode".
# Trebovaniya: rsync
# Istochniki putey berutsya iz VECTOR_DIODE_CFG (rules/vector_diode.yaml) ili ENV-peremennykh.
# ENV:
#   VECTOR_DIODE_CFG=rules/vector_diode.yaml
#   DIODE_INBOX_OWNER=ester
#   DIODE_INBOX_GROUP=ester

set -euo pipefail

CFG="${VECTOR_DIODE_CFG:-rules/vector_diode.yaml}"

# Primitivnyy YAML-parser dlya klyuch: znachenie (bez kavychek, na odnoy stroke)
yaml_val () {
  local key="$1"
  local val
  # Ischem stroku vida: key: "value" ili key: value
  if val="$(grep -E "^[[:space:]]*${key}:[[:space:]]*" "$CFG" | head -n1 | sed -E 's/^[[:space:]]*[^:]+:[[:space:]]*//')" ; then
    # Schischaem kavychki i probely
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"; val="${val#\'}"
    val="$(echo -n "$val" | tr -d '[:space:]')"
    echo "$val"
  else
    echo ""
  fi
}

if [[ ! -f "$CFG" ]]; then
  echo "Config not found: $CFG" >&2
  exit 2
fi

OUTBOX_ENV="${DIODE_OUTBOX_DIR:-}"
INBOX_ENV="${DIODE_INBOX_DIR:-}"

OUTBOX="${OUTBOX_ENV:-$(yaml_val "outbox_dir")}"
INBOX="${INBOX_ENV:-$(yaml_val "inbox_dir")}"

if [[ -z "$OUTBOX" || -z "$INBOX" ]]; then
  echo "Failed to parse outbox/inbox from $CFG" >&2
  exit 3
fi

# Razvorachivaem tildy, esli est
expand_path () {
  local p="$1"
  if [[ "$p" == "~/"* ]]; then
    echo "${HOME}/${p:2}"
  else
    echo "$p"
  fi
}

OUTBOX="$(expand_path "$OUTBOX")"
INBOX="$(expand_path "$INBOX")"

mkdir -p "$OUTBOX" "$INBOX"

# Prava/vladenie INBOX (ne obyazatelno, no pomogaet izbezhat syurprizov)
CHOWN_USER="${DIODE_INBOX_OWNER:-ester}"
CHOWN_GROUP="${DIODE_INBOX_GROUP:-ester}"
if id -u "$CHOWN_USER" >/dev/null 2>&1 ; then
  chown -R "$CHOWN_USER":"$CHOWN_GROUP" "$INBOX" || true
fi

# Odnostoronnee kopirovanie tolko *.json; perenosim (remove-source-files), ne perezapisyvaem suschestvuyuschee.
# --prune-empty-dirs udalyaet pustye katalogi iz spiska peredachi.
rsync -rtvu \
  --ignore-existing \
  --remove-source-files \
  --prune-empty-dirs \
  --include='*.json' \
  --exclude='*' \
  "${OUTBOX}/./" "${INBOX}/"

# Posle uspeshnoy peredachi chistim pustye direktorii v OUTBOX
find "$OUTBOX" -type d -empty -delete 2>/dev/null || true

echo "diode_sync: $(date -u +'%Y-%m-%dT%H:%M:%SZ') synced OUTBOX->INBOX ($OUTBOX -> $INBOX)"
