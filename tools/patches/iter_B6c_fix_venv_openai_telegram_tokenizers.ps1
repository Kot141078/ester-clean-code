#requires -Version 5.0
<#
Ester patch B6d (PS5-safe): fix venv deps (openai + telegram) + resolve chromadb/tokenizers conflict
Explicit bridge: c=a+b -> tsel "Ester startuet" (a) + determinirovannaya protsedura remonta okruzheniya (b) => stabilnyy zapusk (c)
Hidden bridges: Ashby (variety: perebor sovmestimykh transformers), Cover&Thomas (kontrol oshibok cherez freeze/rollback), Gray’s (ne smeshivat "krov": venv otdelno ot sistemnogo Python)
Earth (inzheneriya/anatomiya): kak postavit obratnyy klapan i snyat EKG do vmeshatelstva — snachala "snimok" (pip freeze), potom lechenie, pri oslozhneniyakh otkat.
#>

param(
  [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2

function Write-Ok($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function Write-Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

# --- detect root ---
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
  $here = Split-Path -Parent $MyInvocation.MyCommand.Path
  try { $ProjectRoot = (Resolve-Path (Join-Path $here "..\..")).Path } catch { $ProjectRoot = (Get-Location).Path }
}

if (!(Test-Path $ProjectRoot)) { throw "ProjectRoot not found: $ProjectRoot" }
Push-Location $ProjectRoot

$ts    = Get-Date -Format "yyyyMMdd_HHmmss"
$rbDir = Join-Path $ProjectRoot "tools\patches\_rollback"
if (!(Test-Path $rbDir)) { New-Item -ItemType Directory -Path $rbDir | Out-Null }

$reqPath = Join-Path $ProjectRoot "requirements.txt"
$reqBak  = Join-Path $rbDir "requirements.txt.bak_$ts"

$venvPy  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$freeze  = Join-Path $rbDir "pip_freeze_before_B6d_$ts.txt"

function Ensure-Venv([string]$pyPath){
  if (Test-Path $pyPath) { return }
  Write-Warn "Venv python not found. Creating .venv ..."
  $sysPy = "C:\Python310\python.exe"
  $venvDir = Join-Path $ProjectRoot ".venv"
  if (Test-Path $sysPy) { & $sysPy -m venv $venvDir } else { & python -m venv $venvDir }
  if (!(Test-Path $pyPath)) { throw "Failed to create venv: $pyPath" }
  Write-Ok "Venv created: $pyPath"
}

function Pip-Freeze([string]$py, [string]$outFile){
  & $py -m pip freeze | Out-File -Encoding utf8 $outFile
  Write-Ok "Saved freeze: $outFile"
}

function Rollback([string]$py, [string]$freezeFile){
  Write-Warn "Rollback: restoring packages from freeze..."
  if (Test-Path $freezeFile) {
    & $py -m pip install -r $freezeFile
    Write-Ok "Rollback OK"
  } else {
    Write-Warn "Freeze file not found, cannot rollback packages."
  }
}

function Patch-RequirementsRequests(){
  if (!(Test-Path $reqPath)) { return }
  Copy-Item $reqPath $reqBak -Force
  $raw = Get-Content $reqPath -Raw
  $patched = $raw -replace 'requests\s*>=\s*2\.32\.0','requests>=2.32.5'
  if ($patched -ne $raw) {
    Set-Content -Path $reqPath -Value $patched -Encoding utf8
    Write-Ok "Patched requirements.txt: requests>=2.32.5 (avoid yanked 2.32.0)"
  } else {
    Write-Ok "requirements.txt: requests line unchanged"
  }
}

function Need-ChromaTokenizersFix([string]$py){
  try {
    $out = & $py -m pip show chromadb 2>$null
    if ($LASTEXITCODE -ne 0) { return $false }
    if ($out -match "(?im)^Requires:\s*(.+)$") {
      return ($Matches[1] -match "tokenizers")
    }
  } catch {}
  return $false
}

function Fix-ChromaTokenizers([string]$py){
  Write-Warn "Resolving chromadb/tokenizers conflict: pin tokenizers==0.20.3 and find compatible transformers..."
  $candidates = @(
    "4.52.4","4.51.3","4.50.3","4.49.0","4.48.3","4.47.1","4.46.3","4.45.2",
    "4.44.2","4.43.4","4.42.4","4.41.2","4.40.2","4.39.3","4.38.2","4.37.2",
    "4.36.2","4.35.2","4.34.1"
  )

  foreach ($ver in $candidates) {
    try {
      Write-Warn "Trying transformers==$ver with tokenizers==0.20.3 ..."
      & $py -m pip install --upgrade --force-reinstall "tokenizers==0.20.3" ("transformers==" + $ver)
      Write-Ok ("Pinned OK: transformers==" + $ver + " + tokenizers==0.20.3")
      return
    } catch {
      Write-Warn ("Not compatible: transformers==" + $ver + " (trying older...)")
    }
  }
  throw "Could not find transformers compatible with tokenizers==0.20.3"
}

function Smoke([string]$py){
  $code = @"
import importlib
from importlib import metadata
print("=== B6d SMOKE ===")
mods = ["telegram", "openai", "chromadb", "tokenizers", "transformers"]
for m in mods:
    importlib.import_module(m)
    print("[OK] import", m)
for d in ["python-telegram-bot","openai","chromadb","tokenizers","transformers","requests"]:
    try: print(d+"=="+metadata.version(d))
    except: pass
print("SMOKE: OK")
"@
  & $py -c $code
}

try {
  Write-Ok "ProjectRoot: $ProjectRoot"
  Ensure-Venv $venvPy
  $py = $venvPy

  Pip-Freeze $py $freeze
  Patch-RequirementsRequests

  Write-Ok "Upgrading pip tooling..."
  & $py -m pip install --upgrade pip setuptools wheel

  Write-Ok "Installing missing runtime deps (openai + telegram) and fixing requests..."
  & $py -m pip install --upgrade `
    "requests>=2.32.5" `
    "python-telegram-bot>=20,<22" `
    "openai>=1.0.0" `
    "python-dotenv>=1.0.0" `
    "ddgs>=9.0.0"

  if (Need-ChromaTokenizersFix $py) { Fix-ChromaTokenizers $py } else { Write-Ok "chromadb->tokenizers dependency not detected (skip pin loop)" }

  Smoke $py

  Write-Ok "B6d applied successfully."
  Write-Host "Next run:" -ForegroundColor Cyan
  Write-Host ("  cd " + $ProjectRoot) -ForegroundColor Cyan
  Write-Host "  `$env:PORT='8090'" -ForegroundColor Cyan
  Write-Host "  .\.venv\Scripts\python.exe run_ester_fixed.py" -ForegroundColor Cyan

} catch {
  Write-Err $_.Exception.Message
  Rollback $venvPy $freeze
  throw
} finally {
  Pop-Location
}
