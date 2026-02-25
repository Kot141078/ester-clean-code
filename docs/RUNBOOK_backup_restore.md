# Runbook: Backup/Restore
1) Proverit `/ready` (ok=true) i `/ops/backup/verify` (200).
2) If restoration is needed: ePOST/ops/bachkup/restor ZZF0TSZyo.
3) Check e/provider/status and quick RAG request.
4) Record the vice in the event log.
