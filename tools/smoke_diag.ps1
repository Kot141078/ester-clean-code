Param([string]$Base="http://127.0.0.1:8080")
function Hit([string]$p){ try{ $r=Invoke-WebRequest -Uri ($Base+$p) -UseBasicParsing -TimeoutSec 5; "$p -> $($r.StatusCode)" } catch { "$p -> FAILED: $($_.Exception.Message)" } }
Hit "/_diag/health"
Hit "/_diag/routes"
Hit "/_diag/env"
