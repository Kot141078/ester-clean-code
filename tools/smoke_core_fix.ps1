
Param(
  [string]$Base = "http://127.0.0.1:8080"
)
function ping([string]$u){
  try {
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 6
    "[ok]  {0} -> {1}" -f $u, $r.StatusCode
  } catch {
    "[err] {0} -> {1}" -f $u, $_.Exception.Message
  }
}
ping "$Base/health"
ping "$Base/_alias/favicon.ico"
ping "$Base/_alias/portal"
