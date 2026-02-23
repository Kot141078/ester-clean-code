# tools\fix_register_all_block.ps1
# Repair the top-level register_all try/except block so it's syntactically valid.
# Safety: backup + py_compile check + auto-rollback on failure.

param(
  [string]$ProjectDir = (Get-Location).Path,
  [string]$PyFile = "run_ester_fixed.py"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err ($m){ Write-Host "[ERR ] $m" -ForegroundColor Red }

$path = Join-Path $ProjectDir $PyFile
if (-not (Test-Path $path)) { throw "File not found: $path" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$path.bak_fix_$stamp"
Copy-Item -LiteralPath $path -Destination $bak -Force
Info "Backup: $bak"

# Read file as UTF-8 (tolerant)
$lines = Get-Content -LiteralPath $path -Encoding UTF8

# Find "flask_app = Flask(__name__)"
$idxFlask = -1
for ($i=0; $i -lt $lines.Count; $i++){
  if ($lines[$i] -match '^\s*flask_app\s*=\s*Flask\(__name__\)\s*$'){
    $idxFlask = $i
    break
  }
}
if ($idxFlask -lt 0) { throw "Cannot find: flask_app = Flask(__name__)" }

# Find the start of bypass block (prefer explicit comment, fallback to def)
$idxBypass = -1
for ($i=$idxFlask+1; $i -lt [Math]::Min($lines.Count, $idxFlask+400); $i++){
  if ($lines[$i] -match '^\s*#\s*Sister inbound bypass for request-guards'){
    $idxBypass = $i
    break
  }
}
if ($idxBypass -lt 0){
  for ($i=$idxFlask+1; $i -lt [Math]::Min($lines.Count, $idxFlask+400); $i++){
    if ($lines[$i] -match '^\s*def\s+_bypass_before_request_for_paths\b'){
      $idxBypass = $i
      break
    }
  }
}
if ($idxBypass -lt 0) { throw "Cannot find bypass block start (comment or def _bypass_before_request_for_paths)." }

# Replace everything between flask_app line and bypass start with canonical try/except
$head = @()
if ($idxFlask -ge 0) { $head = $lines[0..$idxFlask] }

$tail = @()
if ($idxBypass -le $lines.Count-1) { $tail = $lines[$idxBypass..($lines.Count-1)] }

$middle = @(
  "",
  "try:",
  "    from modules.register_all import register_all as _register_all",
  "    _register_all(flask_app)",
  "except Exception as e:",
  "    logging.warning(f`"[register_all] not active: {e}`")",
  ""
)

$linesNew = @($head + $middle + $tail)

# Write back UTF-8 no BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($path, $linesNew, $utf8NoBom)
Info "Saved repaired block into: $path"

# Compile check with proper exit-code handling
$py = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Info "Running: $py -m py_compile $PyFile"
& $py -m py_compile $path
if ($LASTEXITCODE -ne 0){
  Err "py_compile FAILED (exit=$LASTEXITCODE). Rolling back."
  Copy-Item -LiteralPath $bak -Destination $path -Force
  throw "Compile failed; restored backup: $bak"
}

Info "OK: py_compile succeeded."