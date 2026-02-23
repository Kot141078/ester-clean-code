param(
  [string]$Base = "http://127.0.0.1:8080"
)
Write-Host "== /live =="
try { iwr -UseBasicParsing "$Base/live" } catch { $_ }

Write-Host "== /ready =="
try { iwr -UseBasicParsing "$Base/ready" } catch { $_ }
