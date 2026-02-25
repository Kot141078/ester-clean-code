param(
  [string]$ProjectRoot = "D:\ester-project",
  [switch]$Rollback
)

$ErrorActionPreference = "Stop"

function Write-Info($m){ Write-Host $m -ForegroundColor Cyan }
function Write-Ok($m){ Write-Host $m -ForegroundColor Green }
function Write-Warn($m){ Write-Host $m -ForegroundColor Yellow }
function Write-Err($m){ Write-Host $m -ForegroundColor Red }

# ==============================
# Ester patch B6 (PS5-safe)
# Explicit bridge: c=a+b -> (a) your venv as a “body” + (c) strict dependency pins => (c) predictable launch
# Hidden bridges: Ashby (reduces the “diversity” of dependencies to manageable), Carpet&Thomas (a channel without the “noise” of conflicts),
# Gry's (seam without necrosis: neat fixation of the version instead of chaotic upgrades)
# Erth (engineering/anatomy): this is how to select compatible threads/steps in a connection - otherwise it will “break the thread” (dependency resolver)
# ==============================

$req = Join-Path $ProjectRoot "requirements.txt"
$py  = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$bakDir = Join-Path $ProjectRoot "tools\patches\_bak"
New-Item -ItemType Directory -Force -Path $bakDir | Out-Null

function Get-LatestStateFile([string]$dir){
  $f = Get-ChildItem -LiteralPath $dir -Filter "B6_state_*.json" -ErrorAction SilentlyContinue |
       Sort-Object Name -Descending | Select-Object -First 1
  if ($null -eq $f) { return $null }
  return $f.FullName
}

function Ensure-Line([string[]]$lines, [string]$rx, [string]$newline){
  $out = New-Object System.Collections.Generic.List[string]
  $replaced = $false
  foreach($ln in $lines){
    if ($ln -match $rx){
      if (-not $replaced){
        $out.Add($newline)
        $replaced = $true
      } else {
        # drop duplicates
      }
    } else {
      $out.Add($ln)
    }
  }
  if (-not $replaced){
    $out.Add($newline)
  }
  return ,$out.ToArray()
}

function Run-Py([string]$args){
  & $py $args
  if ($LASTEXITCODE -ne 0){ throw "Python failed: $args" }
}

if ($Rollback){
  Write-Info "B6 rollback requested..."
  if (!(Test-Path -LiteralPath $bakDir)){ throw "No backup dir: $bakDir" }
  $statePath = Get-LatestStateFile $bakDir
  if ($null -eq $statePath){ throw "No B6_state_*.json found in $bakDir" }

  $stateJson = Get-Content -LiteralPath $statePath -Raw
  $state = $stateJson | ConvertFrom-Json

  if (!(Test-Path -LiteralPath $state.req_backup)){ throw "Missing req backup: $($state.req_backup)" }
  Copy-Item -LiteralPath $state.req_backup -Destination $req -Force
  Write-Ok "requirements.txt restored from: $($state.req_backup)"

  if (Test-Path -LiteralPath $state.freeze_before){
    Write-Info "Reinstalling packages from freeze (best-effort): $($state.freeze_before)"
    & $py "-m" "pip" "install" "-r" $state.freeze_before
    Write-Ok "pip install -r freeze_before done (if pip showed errors — read them)."
  } else {
    Write-Warn "freeze_before missing; only requirements.txt restored."
  }

  Write-Info "[smoke] imports"
  & $py "-c" "import telegram; import chromadb; import tokenizers; import transformers; print('OK telegram', getattr(telegram,'__version__','?'), 'chromadb', getattr(chromadb,'__version__','?'), 'tokenizers', tokenizers.__version__, 'transformers', transformers.__version__)"
  Write-Ok "Rollback complete."
  exit 0
}

# --- apply ---
if (!(Test-Path -LiteralPath $req)){ throw "Not found: $req" }
if (!(Test-Path -LiteralPath $py)){ throw "Not found: $py (venv missing?)" }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$reqBak = Join-Path $bakDir ("requirements.txt.bak_B6_" + $ts)
$freezeBefore = Join-Path $bakDir ("pip_freeze_before_B6_" + $ts + ".txt")
$freezeAfter  = Join-Path $bakDir ("pip_freeze_after_B6_" + $ts + ".txt")
$stateFile    = Join-Path $bakDir ("B6_state_" + $ts + ".json")

Copy-Item -LiteralPath $req -Destination $reqBak -Force
Write-Ok "Backup: $reqBak"

Write-Info "[freeze] before"
& $py "-m" "pip" "freeze" | Out-File -LiteralPath $freezeBefore -Encoding UTF8
Write-Ok "Saved: $freezeBefore"

# Patch requirements.txt (safe pinnings to avoid chromadb/tokenizers conflict + avoid yanked requests)
$lines = Get-Content -LiteralPath $req
$lines = Ensure-Line $lines '^\s*requests(\s*==|\s*>=|\s*<=|\s*~=|\s*$)' "requests==2.32.5"
$lines = Ensure-Line $lines '^\s*tokenizers(\s*==|\s*>=|\s*<=|\s*~=|\s*$)' "tokenizers==0.20.3"
$lines = Ensure-Line $lines '^\s*transformers(\s*==|\s*>=|\s*<=|\s*~=|\s*$)' "transformers==4.45.2"
$lines = Ensure-Line $lines '^\s*sentence-transformers(\s*==|\s*>=|\s*<=|\s*~=|\s*$)' "sentence-transformers==2.7.0"
# telegram is often missing from requirements in Ester dumps; we pin it too:
$lines = Ensure-Line $lines '^\s*python-telegram-bot(\s*==|\s*>=|\s*<=|\s*~=|\s*$)' "python-telegram-bot>=20.0,<22"

Set-Content -LiteralPath $req -Value $lines -Encoding UTF8
Write-Ok "[patch] requirements.txt updated (requests/tokenizers/transformers/sentence-transformers/python-telegram-bot)"

# Save state for rollback
$stateObj = [PSCustomObject]@{
  ts = $ts
  req_backup = $reqBak
  freeze_before = $freezeBefore
  freeze_after = $freezeAfter
}
($stateObj | ConvertTo-Json -Depth 4) | Out-File -LiteralPath $stateFile -Encoding UTF8
Write-Ok "State: $stateFile"

try {
  Write-Info "[pip] upgrade pip"
  & $py "-m" "pip" "install" "--upgrade" "pip"

  Write-Info "[pip] install requirements (this enforces pins)"
  & $py "-m" "pip" "install" "-r" $req

  Write-Info "[pip] sanity: pip check"
  & $py "-m" "pip" "check"

  Write-Info "[freeze] after"
  & $py "-m" "pip" "freeze" | Out-File -LiteralPath $freezeAfter -Encoding UTF8
  Write-Ok "Saved: $freezeAfter"

  Write-Info "[smoke] imports + versions"
  & $py "-c" "import telegram; import chromadb; import tokenizers; import transformers; print('telegram', getattr(telegram,'__version__','?')); print('chromadb', getattr(chromadb,'__version__','?')); print('tokenizers', tokenizers.__version__); print('transformers', transformers.__version__)"
  Write-Info "[smoke] py_compile run_ester_fixed.py"
  & $py "-m" "py_compile" (Join-Path $ProjectRoot "run_ester_fixed.py")

  Write-Ok "B6 OK. Use venv python to run:"
  Write-Host ("  " + $py + " run_ester_fixed.py") -ForegroundColor Green
  Write-Host ("Rollback (if needed): powershell -ExecutionPolicy Bypass -File " + (Join-Path $ProjectRoot "tools\patches\iter_B6_ps5_fix_venv_telegram_and_chroma_tokenizers.ps1") + " -Rollback") -ForegroundColor Yellow
}
catch {
  Write-Err ("B6 FAILED: " + $_.Exception.Message)
  Write-Warn "Auto-rollback: restoring requirements.txt and best-effort pip reinstall from freeze_before..."
  try {
    Copy-Item -LiteralPath $reqBak -Destination $req -Force
    if (Test-Path -LiteralPath $freezeBefore){
      & $py "-m" "pip" "install" "-r" $freezeBefore
    }
    Write-Ok "Rollback done (check pip output)."
  } catch {
    Write-Err ("Rollback also failed: " + $_.Exception.Message)
    Write-Warn ("Manual fallback: restore " + $reqBak + " and use pip install -r " + $freezeBefore)
  }
  exit 1
}
