# Runbook: Vysokaya latentnost
1) Look at Grafan: p95/p99, erroneous moves.
2) Remove k6 short profile (yomake wencho from 60c).
3) Check the LLM provider and the ingest queue.
4) Enable the flag efeature_flags.yaml: kg_repair=three when degrading CG.
5) If necessary - rock from (docker-compose.prod.iml there are no replicas, but you can raise the second node and install DNS RR).
