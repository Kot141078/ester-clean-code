# Runbook: Backup/Restore
1) Proverit `/ready` (ok=true) i `/ops/backup/verify` (200).
2) Esli nuzhno vosstanovlenie: `POST /ops/backup/restore { id: <last-good> }`.
3) Proverit `/providers/status` i bystryy RAG‑zapros.
4) Zafiksirovat tick v zhurnale sobytiy.
