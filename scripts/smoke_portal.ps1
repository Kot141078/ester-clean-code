Param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 8080
)
$base = "http://$Host:$Port"
function ping($url){
  try {
    $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
    "[ok] $url -> $($r.StatusCode)"
  } catch {
    "[err] $url -> $($_.Exception.Message)"
  }
}
ping "$base/"
ping "$base/portal"
ping "$base/favicon.ico"
