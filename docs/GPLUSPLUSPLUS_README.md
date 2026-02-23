# G+++ Guide

## Chto vklyuchili
- **Golden paths**: `/ops/probe/golden` → web-provider v Argo Rollouts Analysis.
- **Recording Rules**: deshevye metriki p95/p99 i error-rate dlya bystrykh zaprosov analayzera.
- **Auto-Failover**: Alertmanager → DR Webhook → vneshnie annotatsii dlya external-dns (ves secondary=100).
- **Mirror-traffic**: Istio VirtualService `mirrorPercentage` → teplyy progrev kanareyki.

## Kak vklyuchit
1. Obnovi prilozhenie: zaregistriruy blueprint `bp_probe` v `app.py`:
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
3. Esli ispolzuesh Istio mirror:
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

## Smoke / Proverki
- `GET /ops/probe/golden` → `{value: 1}` pri zelenom sostoyanii.
- Argo: `kubectl argo rollouts get rollout ester -n ester` — v `analysis.templates` est `*-golden` (dobavlen k SLO).
- DR:
  ```bash
  curl -H 'X-Auth-Token: <SECRET>' \
       -H 'Content-Type: application/json' \
       --data @scripts/alert_test_payload.json \
       http://<dr-webhook-svc>:8080/alert
  ```
  Dolzhen propatchitsya `Service/Ingress` annotatsiyami external-dns (ves/identifikator).

## Primechaniya po sovmestimosti
- Port berem iz `.Values.port`, servis — iz `.Values.service.port`.
- Kanareechnyy servis `{{ fullname }}-canary` uzhe sozdaetsya chartom i ispolzuetsya v Rollout/VirtualService.

_Ester ostaetsya «pamyat + myshlenie + set». Eto — broneplastina dlya prod-kontura._
