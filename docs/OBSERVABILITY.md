# Observability & Release One-Shot (Iteratsiya G)

## 1) Local observability

```bash
docker compose -f docker-compose.observability.yml up -d
# ili
make observability-up
```

Proverki:
- Prometheus http://localhost:9090 → Targets: `ester` **UP**
- Grafana http://localhost:3000 (admin/admin) → dobavlen datasource Prometheus (provisioned)
- `/metrics` otdaet 200: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/metrics`

## 2) Helm-chart (ServiceMonitor/Rules/VirtualService)

```bash
helm upgrade --install ester ./charts/ester -n ester --create-namespace   -f values.observability.yaml
# ili
make helm-apply
```

Ozhidaemye obekty:
```
kubectl get servicemonitor -n ester
kubectl get prometheusrule -n ester
kubectl get virtualservice -n ester
```

## 3) Testy perf/smoke

```bash
pytest -m perf -k metrics -q
pytest -m smoke -q
# ili
make test-perf
make test-smoke
```

## 4) Reliz predprosmotra

```bash
bash scripts/release_preview.sh
# ili
make release-preview
```

Artefakty:
- `CHANGELOG.md`
- yosvom-v0.1-preview.spdh.jsonyo (if the software is installed)
- `ester-0.1-preview.tar.gz`

Vygruzka:
- via estorage.uploader (if the module is available);
- libo WebDAV (peremennye `WEBDAV_URL`, `WEBDAV_USER`, `WEBDAV_PASSWORD`);
- or C3 (SLI ёавсё, variable еС3_БОСКЭТе, optional еС3_PREFIXо).

## Primechaniya

- The values ​​of the Arctic Ocean thresholds are configured in evalues.observabilities.yamlyo.
- For Istio, specify your yoisto.hosto and, if necessary, yoisto.gatewayyo.
- The cluster must have eServiceMonitor/ePrometneusRulee DRCs (Prometneus Operator).
