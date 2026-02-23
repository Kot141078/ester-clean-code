#requires -Version 5.0
<#
Ester patch B6e (PS5-safe): enable PTB JobQueue in venv so VOLITION heartbeat works
Explicit bridge: c=a+b -> "dumanie" (a) + JobQueue/APS scheduler plumbing (b) => avtonomnye tsikly (c)
Hidden bridges: Ashby (variety: vklyuchaem nedostayuschiy kontur), Cover&Thomas (rollback po freeze kak kontrol kanala),
Gray’s (ne smeshivat sredy: venv fiksitsya otdelno ot sistemnogo Python)
Earth (inzheneriya/anatomiya): bez provodimosti v uzle SA serdtse ne zadaet ritm — stavim "provodyaschuyu sistemu" (JobQueue).
#>

param([string]$ProjectRoot = "")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2

function Ok($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  $ProjectRoot = (Resolve-Path (Join-Path $here "..\..")).Path
}

Push-Location $ProjectRoot

$ts    = Get-Date -Format "yyyyMMdd_HHmmss"
$rbDir = Join-Path $ProjectRoot "tools\patches\_rollback"
if (!(Test-Path $rbDir)) { New-Item -ItemType Directory -Path $rbDir | Out-Null }

$py     = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$freeze = Join-Path $rbDir "pip_freeze_before_B6e_$ts.txt"
$smoke  = Join-Path $rbDir "smoke_B6e_$ts.py"

function Rollback([string]$pyPath, [string]$freezeFile){
  Warn "Rollback: restoring packages from freeze..."
  if (Test-Path $freezeFile) {
    & $pyPath -m pip install -r $freezeFile
    Ok "Rollback OK"
  } else {
    Warn "Freeze not found, cannot rollback."
  }
}

try {
  if (!(Test-Path $py)) { throw "Venv python not found: $py" }

  Ok "ProjectRoot: $ProjectRoot"
  & $py -m pip freeze | Out-File -Encoding utf8 $freeze
  Ok "Saved freeze: $freeze"

  Ok "Installing PTB JobQueue extras (adds APScheduler deps)..."
  & $py -m pip install --upgrade 'python-telegram-bot[job-queue]>=21,<22'

  @"
import sys
print("=== B6e SMOKE ===")
from telegram.ext import JobQueue
jq = JobQueue()
print("[OK] JobQueue created:", type(jq).__name__)
import apscheduler
print("[OK] apscheduler:", getattr(apscheduler,"__version__", "n/a"))
print("SMOKE: OK")
"@ | Out-File -Encoding utf8 $smoke

  & $py $smoke

  Ok "B6e applied successfully."
  Write-Host "Next run:" -ForegroundColor Cyan
  Write-Host "  cd $ProjectRoot" -ForegroundColor Cyan
  Write-Host "  `$env:PORT='8090'" -ForegroundColor Cyan
  Write-Host "  .\.venv\Scripts\python.exe run_ester_fixed.py" -ForegroundColor Cyan

} catch {
  Err $_.Exception.Message
  Rollback $py $freeze
  throw
} finally {
  Pop-Location
}
