#!/usr/bin/env bash
# scripts/diode_sync_rsync.sh - odnostoronnyaya sinkhronizatsiya OUTBOX → INBOX dlya "data diode".
# Trebovaniya: rsync
# Path sources are taken from VECTOR_DIODE_KFG (rules/vector_diode.yaml) or ENV variables.
# ENV:
#   VECTOR_DIODE_CFG=rules/vector_diode.yaml
#   DIODE_INBOX_OWNER=ester
#   DIODE_INBOX_GROUP=ester

set -euo pipefail

CFG="${VECTOR_DIODE_CFG:-rules/vector_diode.yaml}"

# A primitive YML parser for key: value (without quotes, on one line)
yaml_val () {
  local key="$1"
  local val
  # Ischem stroku vida: key: "value" ili key: value
  if val="$(grep -E "^[[:space:]]*${key}:[[:space:]]*" "$CFG" | head -n1 | sed -E 's/^[[:space:]]*[^:]+:[[:space:]]*//')" ; then
    # Remove quotes and spaces
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

# Expand tildes, if any
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

# INBOX Rights/Ownership (not required, but helps avoid surprises)
CHOWN_USER="${DIODE_INBOX_OWNER:-ester}"
CHOWN_GROUP="${DIODE_INBOX_GROUP:-ester}"
if id -u "$CHOWN_USER" >/dev/null 2>&1 ; then
  chown -R "$CHOWN_USER":"$CHOWN_GROUP" "$INBOX" || true
fi

# Single-sided copying *.zhsion only; we transfer (remove-source-files), we do not overwrite the existing one.
# --prune-empty-dirs Removes empty directories from the transfer list.
rsync -rtvu \
  --ignore-existing \
  --remove-source-files \
  --prune-empty-dirs \
  --include='*.json' \
  --exclude='*' \
  "${OUTBOX}/./" "${INBOX}/"

# After a successful transfer, we clean empty directories in OTBOKs
find "$OUTBOX" -type d -empty -delete 2>/dev/null || true

echo "diode_sync: $(date -u +'%Y-%m-%dT%H:%M:%SZ') synced OUTBOX->INBOX ($OUTBOX -> $INBOX)"
