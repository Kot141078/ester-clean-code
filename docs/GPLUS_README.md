# G+ Deploy Guide

## 1) Helm install
```bash
bash scripts/helm_install.sh
```

## 2) Vklyuchit canary ili blue-green (Argo Rollouts)
```bash
bash scripts/helm_canary_flip.sh       # canary
bash scripts/helm_bluegreen_switch.sh  # blue-green
```

## 3) Istio (opts.)
Dobav `--set istio.enabled=true --set istio.host=ester.example.com` i ubedis, chto `VirtualService` sozdan chartom. Argo Rollouts budet menyat vesa marshruta `ester-route`.

## 4) SLO i alerty
PrometheusRule sozdaetsya chartom. Alertmanager konfig — `alertmanager/alertmanager.yml.tmpl` (Telegram, PagerDuty, e-mail).

## 5) Unleash
* Saydkar po umolchaniyu v Pod (`.Values.unleash.enabled=true`).
* Standalone-rezhim: vklyuchi `--set unleash.standalone=true` — podnimetsya otdelnyy `Deployment` i `Service` na `:4242`.

## 6) OPA Gatekeeper
Ustanovi Gatekeeper (CRD/kontroller), zatem primenyay manifesty iz `k8s/gatekeeper/`.

## 7) LAN rasprostranenie
Bare-metal: `docker-compose -f lan/docker-compose.lan.yml up -d` ili `systemd-ester-lan-peer.service`.
K8s: dlya obnaruzheniya ispolzuy headless Service + Endpoints ili mesh (Istio/Linkerd).

## 8) Bezopasnost
`NetworkPolicy` ogranichivaet iskhodyaschiy trafik (53/443); `seccomp`/`AppArmor`/`drop ALL`; `runAsNonRoot`.

## 9) Samovosstanovlenie
K8s perezapuskaet pod (liveness/readiness + HPA + PDB). Dlya bare-metal — `systemd` `Restart=always`.

«Ester» — ne prosto chat; eto **pamyat + myshlenie + set**.
