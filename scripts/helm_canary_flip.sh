#!/usr/bin/env bash
set -euo pipefail
REL=${REL:-ester}; NS=${NS:-ester}
helm upgrade "$REL" charts/ester -n "$NS" --reuse-values   --set progressive.canary.enabled=true   --set progressive.blueGreen.enabled=false
