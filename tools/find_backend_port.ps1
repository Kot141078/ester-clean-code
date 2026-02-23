# tools/find_backend_port.ps1
param([int[]]$Ports=@(8080,8010,8000,5000))
$found = $null
foreach($p in $Ports){
  try{
    $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$p/chat/health" -TimeoutSec 3
    if($r.StatusCode -eq 200 -and ($r.Content -match '"ok"\s*:\s*true')){
      $found = $p; break
    }
  }catch{}
}
if($found){ Write-Host "BACKEND PORT = $found"; exit 0 } else { Write-Host "NOT FOUND"; exit 1 }
