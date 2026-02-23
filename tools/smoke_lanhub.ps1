Param([string]$Base="http://127.0.0.1:8080")
function Hit([string]$p){ try{ $r=Invoke-WebRequest -Uri ($Base+$p) -UseBasicParsing -TimeoutSec 5; "$p -> $($r.StatusCode) $($r.Content)" } catch { "$p -> FAILED: $($_.Exception.Message)" } }
Hit "/_lan/status"
try{ $r=Invoke-WebRequest -Uri ($Base+"/_lan/touch") -Method Post -UseBasicParsing -TimeoutSec 5; "/_lan/touch -> $($r.StatusCode) $($r.Content)" } catch { "/_lan/touch -> FAILED: $($_.Exception.Message)" }
