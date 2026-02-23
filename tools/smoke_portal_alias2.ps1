
Param([string]$Base = "http://127.0.0.1:8080")
function ping([string]$u){
  try{ $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 6 -Uri $u; "[ok]  {0} -> {1}" -f $u,$r.StatusCode }
  catch{ "[err] {0} -> {1}" -f $u,$_.Exception.Message }
}
ping "$Base/_alias/portal/health"
ping "$Base/_alias/portal"
ping "$Base/_alias/favicon.ico"
ping "$Base/_alias/favicon/ping"
