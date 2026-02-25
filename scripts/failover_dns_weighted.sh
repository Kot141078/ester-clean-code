#!/usr/bin/env bash
set -euo pipefail

# Switching DNS weight (external-dns, Route53/CloudDNS/Cloudflare - use the necessary annotations).
# Primer:
#   RES=svc/ester NS=ester ID=ester-primary WEIGHT=100 ./failover_dns_weighted.sh

RES=${RES:-svc/ester}
NS=${NS:-ester}
ID=${ID:-ester-primary}
WEIGHT=${WEIGHT:-100}

kubectl annotate "$RES" -n "$NS"   external-dns.alpha.kubernetes.io/set-identifier="$ID"   external-dns.alpha.kubernetes.io/aws-weight="$WEIGHT"   --overwrite
