#!/usr/bin/env bash
set -euo pipefail

# A simple external watcher that aborts the rollout when thresholds are exceeded.
# Requirements: curl, lcd, cubectl + argo-rollouts plugin.
# Peremennye okruzheniya:
#   ROLLOUT, NS, PROM, P99, ERR, INTERVAL

ROLLOUT=${ROLLOUT:-ester}
NS=${NS:-ester}
PROM=${PROM:-http://prometheus-operated.monitoring.svc.cluster.local:9090}
P99=${P99:-5}
ERR=${ERR:-0.01}
INTERVAL=${INTERVAL:-60}

while true; do
  p99=$(curl -sfG "$PROM/api/v1/query"         --data-urlencode 'query=histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{job="ester"}[5m])) by (le))'         | jq -r '.data.result[0].value[1] // 0')
  er=$(curl -sfG "$PROM/api/v1/query"         --data-urlencode 'query=sum(rate(http_requests_total{job="ester",code=~"5.."}[5m]))/clamp_min(sum(rate(http_requests_total{job="ester"}[5m])),1)'         | jq -r '.data.result[0].value[1] // 0')
  echo "[watch] p99=$p99 err=$er"
  # abortion if exceeded any threshold
  awk "BEGIN {exit !($p99 > $P99 || $er > $ERR)}" || {
    echo "[watch] thresholds exceeded — aborting rollout" >&2
    kubectl argo rollouts abort "$ROLLOUT" -n "$NS" || true
  }
  sleep "$INTERVAL"
done
