$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[OK]  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root     = Split-Path -Parent $toolsDir

$mem = Join-Path $root "data\memory\memory.json"
if(-not (Test-Path $mem)){
  Warn "Not found: $mem (ok, nothing to repair)"
  exit 0
}

$stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$bad   = "$mem.corrupt_$stamp"
$bak   = "$mem.bak_$stamp"

Copy-Item $mem $bak -Force
Info "Backup copy: $bak"

Move-Item $mem $bad -Force
Ok "Quarantined: $bad"

# fresh empty json
Set-Content -Path $mem -Value "{}" -Encoding UTF8
Ok "Created new empty: $mem"