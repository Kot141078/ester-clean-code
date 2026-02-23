# PS5‑sovmestimyy smouk‑test portala i favicon
Param(
  [string]$BaseUrl = "http://127.0.0.1:8080"
)
function Hit([string]$Path) {
  try {
    $r = Invoke-WebRequest -Uri ($BaseUrl + $Path) -UseBasicParsing -TimeoutSec 10
    "{0} -> {1}" -f $Path, $r.StatusCode
  } catch {
    "{0} -> FAILED: {1}" -f $Path, $_.Exception.Message
  }
}
Hit "/"
Hit "/favicon.ico"
Hit "/portal"
Hit "/portal/health"
