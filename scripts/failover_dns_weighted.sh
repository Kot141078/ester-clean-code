#!/usr/bin/env bash
set -euo pipefail

# Pereklyuchenie vesa DNS (external-dns, Route53/CloudDNS/Cloudflare — ispolzuyte nuzhnye annotatsii).
# Primer:
#   RES=svc/ester NS=ester ID=ester-primary WEIGHT=100 ./failover_dns_weighted.sh

RES=${RES:-svc/ester}
NS=${NS:-ester}
ID=${ID:-ester-primary}
WEIGHT=${WEIGHT:-100}

kubectl annotate "$RES" -n "$NS"   external-dns.alpha.kubernetes.io/set-identifier="$ID"   external-dns.alpha.kubernetes.io/aws-weight="$WEIGHT"   --overwrite
