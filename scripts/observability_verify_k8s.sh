#!/usr/bin/env bash
set -euo pipefail

NS="${1:-ester}"

echo "[verify-k8s] Namespace: ${NS}"

need_fail=0

check_obj () {
  local kind="$1"
  local name_pattern="$2"
  if ! kubectl get "${kind}" -n "${NS}" 1>/dev/null; then
    echo "[verify-k8s] ERROR: ${kind} list failed"
    need_fail=1
    return
  fi
  if ! kubectl get "${kind}" -n "${NS}" | grep -E "${name_pattern}" >/dev/null; then
    echo "[verify-k8s] ERROR: ${kind} matching '${name_pattern}' not found"
    need_fail=1
  else
    echo "[verify-k8s] OK: ${kind} has '${name_pattern}'"
  fi
}

# Proveryaem klyuchevye CRD-obekty iz charta Ester
check_obj "servicemonitor" "$(kubectl get servicemonitor -n "${NS}" --no-headers 2>/dev/null | awk '{print $1}' | head -n1 || echo ester)"
check_obj "prometheusrule" "$(kubectl get prometheusrule -n "${NS}" --no-headers 2>/dev/null | awk '{print $1}' | grep -E 'slo|rr' || true)"
check_obj "virtualservice" "$(kubectl get virtualservice -n "${NS}" --no-headers 2>/dev/null | awk '{print $1}' | head -n1 || echo ester)"

# Proverim, chto servis publikuet port, i mozhno poluchit kod 200 ot /metrics ili /metrics/prom cherez pod exec
echo "[verify-k8s] Probing /metrics endpoints via a running pod..."
POD="$(kubectl get pod -n "${NS}" -l app.kubernetes.io/name=ester -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [[ -z "${POD}" ]]; then
  echo "[verify-k8s] WARN: no Ester pod found in namespace ${NS}"
else
  set +e
  kubectl exec -n "${NS}" "${POD}" -- sh -lc 'apk add --no-cache curl >/dev/null 2>&1 || true;     (curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/metrics || echo "000")' | grep -qE '200'
  code_metrics=$?
  kubectl exec -n "${NS}" "${POD}" -- sh -lc 'apk add --no-cache curl >/dev/null 2>&1 || true;     (curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/metrics/prom || echo "000")' | grep -qE '200'
  code_prom=$?
  set -e
  if [[ $code_metrics -ne 0 && $code_prom -ne 0 ]]; then
    echo "[verify-k8s] ERROR: neither /metrics nor /metrics/prom returned 200 inside pod"
    need_fail=1
  else
    echo "[verify-k8s] OK: at least one metrics endpoint returns 200"
  fi
fi

if [[ "${need_fail}" -ne 0 ]]; then
  echo "[verify-k8s] FAILED"
  exit 1
fi

echo "[verify-k8s] OK"
