param([switch]$DryRun)

$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[OK]  $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err($m){  Write-Host "[ERR]  $m" -ForegroundColor Red }

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root     = Split-Path -Parent $toolsDir
$target   = Join-Path $root "run_ester_fixed.py"

if(-not (Test-Path $target)){ throw "Not found: $target" }

$raw = Get-Content $target -Raw -Encoding UTF8
if($raw -match "VolitionSystem\.social_synapse_cycle\s*="){
  Ok "Binding already present. Nothing to do."
  exit 0
}

if($raw -notmatch "async\s+def\s+social_synapse_cycle\s*\("){
  Warn "No top-level social_synapse_cycle() found in $target. Nothing to bind."
  exit 0
}

$stamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$bak   = "$target.bak_$stamp"
Copy-Item $target $bak -Force
Info "Backup: $bak"

$append = @'

# --- HOTFIX: bind standalone cycles to VolitionSystem (so life_tick can call them safely) ---
try:
    if "VolitionSystem" in globals() and "social_synapse_cycle" in globals():
        if not hasattr(VolitionSystem, "social_synapse_cycle"):
            VolitionSystem.social_synapse_cycle = social_synapse_cycle  # type: ignore
except Exception:
    pass
'@

if($DryRun){
  Info "DryRun: not writing."
  exit 0
}

Add-Content -Path $target -Value $append -Encoding UTF8
Ok "Appended binding hotfix."

Info "py_compile..."
& python -m py_compile $target
if($LASTEXITCODE -ne 0){
  Err "py_compile FAILED -> rollback"
  Copy-Item $bak $target -Force
  exit 1
}

Ok "py_compile OK"
Info "Done."