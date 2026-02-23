param(
  [int]$Port=8080,
  [string]$SrvHost='127.0.0.1'
)
$base = "http://$SrvHost`:$Port"

Write-Host "== Providers =="
try { iwr -UseBasicParsing "$base/providers/status" } catch { $_ }

Write-Host "== Routes (should be 200) =="
try { iwr -UseBasicParsing "$base/routes" } catch { $_ }

Write-Host "== RAG Status (200 if hybrid or soft mode) =="
try { iwr -UseBasicParsing "$base/rag/status" } catch { $_ }

Write-Host "== Where (debug) =="
try { iwr -UseBasicParsing "$base/_where" } catch { $_ }
