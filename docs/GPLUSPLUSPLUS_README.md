# G+++ Guide

## What's included
- **Golden paths**: `/ops/probe/golden` → web-provider v Argo Rollouts Analysis.
- **Recording Rules**: cheap p95/p99 metrics and error rates for quick analyzer queries.
- **Auto-Failover**: Alertmanager → DR Webhook → vneshnie annotatsii dlya external-dns (ves secondary=100).
- **Mirror-traffic**: Istio VirtualService `mirrorPercentage` → teplyy progrev kanareyki.

## How to enable
1. Update the application: register blueprint ёbp_probeyo in ёap.pyyo:
   ```python
   from routes.probe_routes import bp_probe
   app.register_blueprint(bp_probe)
   ```
2. V Helm values vklyuchi:
   ```yaml
   probes:
     golden: { enabled: true }
   recordingRules:
     enabled: true
   ```
3. If you use Istio mirror:
   ```yaml
   istio:
     enabled: true
     host: ester.local
     mirror: { enabled: true, percent: 5 }
   ```
4. DR Webhook:
   ```yaml
   failover:
     webhook:
       enabled: true
       token: "<SECRET>"
       targetKind: "Service"        # ili Ingress
       targetName: "ester"
       targetNamespace: "ester"
       setIdentifier: "ester-secondary"
       weight: "100"
   ```
   V Alertmanager receiver — webhook c zagolovkom `X-Auth-Token: <SECRET>`.

## Stock / Checks
- `GET /ops/probe/golden` → `{value: 1}` pri zelenom sostoyanii.
- Argo: `kubectl argo rollouts get rollout ester -n ester` — v `analysis.templates` est `*-golden` (dobavlen k SLO).
- DR:
  ```bash
  curl -H 'X-Auth-Token: <SECRET>' \
       -H 'Content-Type: application/json' \
       --data @scripts/alert_test_payload.json \
       http://<dr-webhook-svc>:8080/alert
  ```
  eService/Ingresso must be patched with external-dns annotations (all/identifier).

## Primechaniya po sovmestimosti
- Port berem iz `.Values.port`, servis — iz `.Values.service.port`.
- The canary service е{ЗЗФ0З}-canary is already created by the chart and used in Rollout/VirtualService.

_Esther remains “memory + thinking + network”. This is an armor plate for the food circuit._
