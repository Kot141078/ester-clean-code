#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ROLLOUT=ester NS=ester ./chatops_rollouts.sh status|promote|abort|pause|resume|undo

ROLLOUT=${ROLLOUT:-ester}
NS=${NS:-ester}
CMD=${1:-status}

case "$CMD" in
  status)  kubectl argo rollouts get rollout "$ROLLOUT" -n "$NS" ;;
  promote) kubectl argo rollouts promote "$ROLLOUT" -n "$NS" ;;
  abort)   kubectl argo rollouts abort "$ROLLOUT" -n "$NS" ;;
  pause)   kubectl argo rollouts pause "$ROLLOUT" -n "$NS" ;;
  resume)  kubectl argo rollouts resume "$ROLLOUT" -n "$NS" ;;
  undo)    kubectl argo rollouts undo "$ROLLOUT" -n "$NS" ;;
  *) echo "Usage: $0 {status|promote|abort|pause|resume|undo}" >&2; exit 2 ;;
esac
