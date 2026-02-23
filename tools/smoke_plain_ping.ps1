Param([string]$Base="http://127.0.0.1:8080")
try{ $r=Invoke-WebRequest -Uri ($Base+"/_ping") -UseBasicParsing -TimeoutSec 5; "/_ping -> $($r.StatusCode) $($r.Content)" } catch { "/_ping -> FAILED: $($_.Exception.Message)" }
