# ab_guard.ps1 — zapusk s A/B-slotom i avto-otkatom po 3 bystrym health-proverkam
param(
  [ValidateSet("A","B")][string]$Slot = "A",
  [string]$Host = "127.0.0.1",
  [int]$Port = 8137,
  [string]$App = ".\app.py"
)
$ErrorActionPreference = "Stop"
function Ping-Health($url){
  try {
    $resp = Invoke-WebRequest -Uri $url -TimeoutSec 2 -UseBasicParsing
    return ($resp.StatusCode -eq 200)
  } catch { return $false }
}
Write-Host "[ab-guard] Slot=$Slot, $Host:$Port" -ForegroundColor Cyan
$env:AB_MODE = $Slot
$job = Start-Process -FilePath "py" -ArgumentList @("-3", $App) -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 1
$ok = $false
for ($i=0; $i -lt 3; $i++){
  Start-Sleep -Seconds 2
  if (Ping-Health "http://$Host:$Port/health"){ $ok = $true; break }
}
if (-not $ok){
  Write-Host "[rollback] Slot $Slot ne proshel health; pereklyuchayus..." -ForegroundColor Yellow
  Stop-Process -Id $job.Id -Force
  $Slot = ($Slot -eq "A") ? "B" : "A"
  $env:AB_MODE = $Slot
  $job = Start-Process -FilePath "py" -ArgumentList @("-3", $App) -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 3
  if (Ping-Health "http://$Host:$Port/health")){
    Write-Host "[ok] Udalos podnyat na zapasnom slote $Slot" -ForegroundColor Green
  } else {
    Write-Host "[fail] Oba slota ne vzleteli. Proverte logi." -ForegroundColor Red
  }
}
