# Observability & Release One-Shot (Iteratsiya G)

## 1) Lokalnaya nablyudaemost

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
- `sbom-v0.1-preview.spdx.json` (esli ustanovlen syft)
- `ester-0.1-preview.tar.gz`

Vygruzka:
- cherez `storage.uploader` (esli modul dostupen);
- libo WebDAV (peremennye `WEBDAV_URL`, `WEBDAV_USER`, `WEBDAV_PASSWORD`);
- libo S3 (CLI `aws`, peremennaya `S3_BUCKET`, optsionalno `S3_PREFIX`).

## Primechaniya

- Znacheniya porogov SLO nastraivayutsya v `values.observability.yaml`.
- Dlya Istio ukazhite svoy `istio.host` i, pri neobkhodimosti, `istio.gateway`.
- V klastere dolzhny byt CRD `ServiceMonitor`/`PrometheusRule` (Prometheus Operator).
