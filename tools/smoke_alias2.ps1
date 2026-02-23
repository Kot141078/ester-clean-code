Param([string]$Base="http://127.0.0.1:8080")
function Hit([string]$p){ try{ $r=Invoke-WebRequest -Uri ($Base+$p) -UseBasicParsing -TimeoutSec 5; "$p -> $($r.StatusCode)" } catch { "$p -> FAILED: $($_.Exception.Message)" } }
Hit "/_alias/portal/health"
Hit "/_alias/portal"
Hit "/_alias/favicon.ico"
