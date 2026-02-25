# G+ Deploy Guide

## 1) Helm install
```bash
bash scripts/helm_install.sh
```

## 2) Turn on canaries or blue-greens (Argo Rollouts)
```bash
bash scripts/helm_canary_flip.sh       # canary
bash scripts/helm_bluegreen_switch.sh  # blue-green
```

## 3) Istio (opts.)
Addav `--set istio.enabled=true --set istio.host=ester.example.com` i ubedis, chto `VirtualService` sozdan chartom. Argo Rollouts will be changed vesa route `ester-route`.

## 4) SLO i alerty
PrometneusRulier is created by a chart. Alertmanager config - yoalertmanager/alertmanager.iml.tmplyo (Telegram, PagerDuty, e-mail).

## 5) Unleash
* Sidecar by default is in Under (e.Values.unlash.enabled=three).
* Standalone mode: turn on the e-network unlash.standalone=three - a separate eDeployment and eService will rise to e:4242e.

## 6) OPA Gatekeeper
Ustanovi Gatekeeper (CRD/kontroller), zatem primenyay manifesty iz `k8s/gatekeeper/`.

## 7) LAN rasprostranenie
Bare-metal: `docker-compose -f lan/docker-compose.lan.yml up -d` ili `systemd-ester-lan-peer.service`.
K8s: for detection use headless Service + Endpoints or mesh (Istio/Linkerd).

## 8) Bezopasnost
eNetworkPolice limits outgoing traffic (53/443); yosetskompyo/yoAppArmore/yodrop ALLYo; YorunAsNonRoote.

## 9) Samovosstanovlenie
K8s restarts under (liveness/rediness + NPA + PDB). For bar metal - ёsystemdyo ёRestart=alvayse.

“Esther” is not just a chat; it's **memory + thinking + network**.
