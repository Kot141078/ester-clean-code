<#
tools\run_ester_utf8.ps1 — zapusk Ester v Windows s zhestkoy UTF-8 distsiplinoy

YaVNYY MOST: c=a+b -> “pamyat/logi (b) dolzhny byt chitaemy cheloveku (a)”: esli konsol lomaet kirillitsu, svyaz rvetsya.
SKRYTYE MOSTY:
  - Ashby (requisite variety): odin istochnik istiny po kodirovke snizhaet khaos variantov (OEM/ANSI/UTF-8).
  - Cover&Thomas: kodirovka — eto kanal; nevernyy dekoder = shum, padaet propusknaya sposobnost smysla.

ZEMNOY ABZATs (inzheneriya/anatomiya):
  Eto kak maska s nepravilnym filtrom: kislorod (tekst) est, no esli “filtr” (kodovaya stranitsa) ne tot — mozg vidit gipoksiyu (krakozyabry).
#>

[CmdletBinding()]
param(
  [string]$HostIP = "0.0.0.0",
  [int]$Port = 8090
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Ok($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function Write-Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

# --- Project root: tools\this.ps1 -> root is parent of tools ---
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $root

# --- Force console to UTF-8 (fix mojibake) ---
try {
  & chcp 65001 | Out-Null
} catch {
  Write-Warn "chcp 65001 failed (not fatal): $($_.Exception.Message)"
}

try {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [Console]::InputEncoding  = $utf8NoBom
  [Console]::OutputEncoding = $utf8NoBom
  $global:OutputEncoding    = $utf8NoBom
  Write-Ok "Console encoding forced to UTF-8 (cp65001)."
} catch {
  Write-Warn "Console encoding set failed (not fatal): $($_.Exception.Message)"
}

# --- Force Python UTF-8 mode / stdio ---
$env:PYTHONUTF8       = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$env:HOST             = $HostIP
$env:PORT             = "$Port"

# --- Activate venv if present ---
$venvActivate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
  . $venvActivate
  Write-Ok "Activated venv: .venv"
} else {
  Write-Warn "No venv found at .venv. Running with system Python."
}

# --- Run Ester entrypoint ---
$entry = Join-Path $root "run_ester_fixed.py"
if (-not (Test-Path $entry)) {
  Write-Err "Entrypoint not found: $entry"
  exit 2
}

# Important: in PowerShell the $var:$c construction is parsed as “namespace”, so we use $() for gluing.
Write-Ok ("Starting Ester on {0}:{1} ..." -f $HostIP, $Port)

# -X utf8: force UTF-8 mode inside Python (belt + suspenders)
python -X utf8 $entry
