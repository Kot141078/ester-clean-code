# Runbook: Vysokaya latentnost
1) Posmotret Grafana: p95/p99, oshibochnye kody.
2) Snyat k6 short‑profile (`make bench` s 60s).
3) Proverit provaydera LLM i ochered ingest.
4) Vklyuchit flag `feature_flags.yaml: kg_repair=true` pri degradatsii KG.
5) Pri neobkhodimosti — scale out (docker-compose.prod.yml replikas net, no mozhno podnyat vtoroy uzel i postavit DNS RR).
