<#
tools\run_ester_utf8.ps1 — запуск Эстер в Windows с жёсткой UTF-8 дисциплиной

ЯВНЫЙ МОСТ: c=a+b -> “память/логи (b) должны быть читаемы человеку (a)”: если консоль ломает кириллицу, связь рвётся.
СКРЫТЫЕ МОСТЫ:
  - Ashby (requisite variety): один источник истины по кодировке снижает хаос вариантов (OEM/ANSI/UTF-8).
  - Cover&Thomas: кодировка — это канал; неверный декодер = шум, падает пропускная способность смысла.

ЗЕМНОЙ АБЗАЦ (инженерия/анатомия):
  Это как маска с неправильным фильтром: кислород (текст) есть, но если “фильтр” (кодовая страница) не тот — мозг видит гипоксию (кракозябры).
#>

[CmdletBinding()]
param(
  [string]$HostIP = "",
  [int]$Port = 0,
  [string]$EntryScript = "run_ester_fixed.py",
  [string]$EnableFlask = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Ok($m){ Write-Host "[OK]  $m" -ForegroundColor Green }
function Write-Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m){ Write-Host "[ERR] $m" -ForegroundColor Red }

function Set-EnvDefault([string]$Name, [string]$Value) {
  $current = [Environment]::GetEnvironmentVariable($Name, "Process")
  if ([string]::IsNullOrWhiteSpace($current)) {
    [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
  }
}

function Get-VenvHome([string]$CfgPath) {
  if (!(Test-Path $CfgPath)) { return $null }
  foreach ($line in Get-Content -Path $CfgPath) {
    if ($line -match '^\s*home\s*=\s*(.+?)\s*$') {
      return $Matches[1].Trim()
    }
  }
  return $null
}

function Add-EnvPathPrefix([string]$Name, [string]$Prefix) {
  if ([string]::IsNullOrWhiteSpace($Prefix) -or !(Test-Path $Prefix)) { return }
  $current = [Environment]::GetEnvironmentVariable($Name, "Process")
  $parts = @()
  if ($current) {
    $parts = $current -split ';' | Where-Object { $_ }
  }
  $normalizedPrefix = [System.IO.Path]::GetFullPath($Prefix)
  $filtered = @($normalizedPrefix)
  foreach ($item in $parts) {
    try {
      $normalizedItem = [System.IO.Path]::GetFullPath($item)
    } catch {
      $normalizedItem = $item
    }
    if ($normalizedItem -ieq $normalizedPrefix) { continue }
    $filtered += $item
  }
  [Environment]::SetEnvironmentVariable($Name, ($filtered -join ';'), "Process")
}

# --- Project root: tools\this.ps1 -> root is parent of tools ---
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $root

function Resolve-ProjectPath([string]$Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
  if ([System.IO.Path]::IsPathRooted($Value)) {
    return [System.IO.Path]::GetFullPath($Value)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $root $Value))
}

if ([string]::IsNullOrWhiteSpace($HostIP)) {
  $HostIP = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
}
if ($Port -le 0) {
  $Port = if ($env:PORT) { [int]$env:PORT } else { 8090 }
}

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
Set-EnvDefault -Name "ESTER_ROOT" -Value $root

if ($EntryScript -ieq "run_ester_fixed.py") {
  if (-not [string]::IsNullOrWhiteSpace($EnableFlask)) {
    $env:ESTER_FLASK_ENABLE = $EnableFlask
  } elseif ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("ESTER_FLASK_ENABLE", "Process"))) {
    $env:ESTER_FLASK_ENABLE = "0"
  }
  if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("ESTER_UI_AUTOLAUNCH", "Process"))) {
    $env:ESTER_UI_AUTOLAUNCH = "0"
  }
  if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable("ESTER_HEADLESS", "Process"))) {
    $env:ESTER_HEADLESS = "1"
  }
  Write-Ok ("Flask/listener mode: ESTER_FLASK_ENABLE={0}" -f $env:ESTER_FLASK_ENABLE)
}

# --- Resolve base Python and inject venv runtime without the redirector ---
$venvRoot = Join-Path $root ".venv"
$venvCfg = Join-Path $venvRoot "pyvenv.cfg"
$venvScripts = Join-Path $venvRoot "Scripts"
$venvSite = Join-Path $venvRoot "Lib\site-packages"
$bootstrap = Join-Path $here "bootstrap_venv_run.py"
$pythonHome = Get-VenvHome $venvCfg
$pythonExe = $null
if ($pythonHome) {
  $candidate = Join-Path $pythonHome "python.exe"
  if (Test-Path $candidate) {
    $pythonExe = $candidate
  }
}
if (-not $pythonExe) {
  if (Test-Path $venvRoot) {
    Write-Err "Base Python from pyvenv.cfg not found. Refusing PATH fallback because it can mix environments."
    exit 3
  }
  $pythonExe = "python"
  Write-Warn "No .venv detected. Falling back to PATH python."
} else {
  Write-Ok "Using base Python: $pythonExe"
}

if (Test-Path $venvRoot) {
  $env:VIRTUAL_ENV = $venvRoot
  Add-EnvPathPrefix -Name "PATH" -Prefix $venvScripts
  $env:PYTHONNOUSERSITE = "1"
  Write-Ok "Prepared isolated venv runtime without redirector."
} else {
  Write-Warn "No venv found at .venv. Running with base environment only."
}

# --- Memory core defaults / safe bootstrap ---
$memoryCoreDefault = Join-Path $root "data\memory_core\ester_memory.sqlite"
$memoryShadowDefault = Join-Path $root "data\memory_core\shadow_compare.jsonl"
Set-EnvDefault -Name "ESTER_MEMORY_CORE_ENABLED" -Value "1"
Set-EnvDefault -Name "ESTER_MEMORY_CORE_DUAL_WRITE" -Value "1"
Set-EnvDefault -Name "ESTER_MEMORY_CORE_READ_CUTOVER" -Value "0"
Set-EnvDefault -Name "ESTER_MEMORY_CORE_SHADOW_READ" -Value "0"
Set-EnvDefault -Name "ESTER_MEMORY_CORE_PATH" -Value $memoryCoreDefault
Set-EnvDefault -Name "ESTER_MEMORY_CORE_SHADOW_LOG" -Value $memoryShadowDefault

$memoryCorePath = Resolve-ProjectPath ([Environment]::GetEnvironmentVariable("ESTER_MEMORY_CORE_PATH", "Process"))
$memoryShadowPath = Resolve-ProjectPath ([Environment]::GetEnvironmentVariable("ESTER_MEMORY_CORE_SHADOW_LOG", "Process"))
[Environment]::SetEnvironmentVariable("ESTER_MEMORY_CORE_PATH", $memoryCorePath, "Process")
[Environment]::SetEnvironmentVariable("ESTER_MEMORY_CORE_SHADOW_LOG", $memoryShadowPath, "Process")
$memoryImporter = Join-Path $here "memory_core_import.py"
$forceMemoryImport = ([Environment]::GetEnvironmentVariable("ESTER_MEMORY_CORE_FORCE_IMPORT", "Process") -eq "1")
$memoryCoreEnabled = ([Environment]::GetEnvironmentVariable("ESTER_MEMORY_CORE_ENABLED", "Process") -notin @("0","false","False","no","off"))

if ($memoryCoreEnabled) {
  Write-Ok ("Memory core env: enabled={0} dual_write={1} cutover={2} shadow={3}" -f `
    $env:ESTER_MEMORY_CORE_ENABLED, `
    $env:ESTER_MEMORY_CORE_DUAL_WRITE, `
    $env:ESTER_MEMORY_CORE_READ_CUTOVER, `
    $env:ESTER_MEMORY_CORE_SHADOW_READ)

  if (!(Test-Path (Split-Path -Parent $memoryCorePath))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $memoryCorePath) | Out-Null
  }
  if (!(Test-Path (Split-Path -Parent $memoryShadowPath))) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $memoryShadowPath) | Out-Null
  }

  $needMemoryImport = $forceMemoryImport -or !(Test-Path $memoryCorePath)
  if ($needMemoryImport -and (Test-Path $memoryImporter)) {
    try {
      Write-Ok "Bootstrapping sidecar memory core ..."
      & $pythonExe -X utf8 $memoryImporter
      if ($LASTEXITCODE -eq 0) {
        Write-Ok ("Memory core ready: {0}" -f $memoryCorePath)
      } else {
        Write-Warn ("Memory core bootstrap failed with exit code {0}. Continuing on legacy memory path." -f $LASTEXITCODE)
      }
    } catch {
      Write-Warn "Memory core bootstrap failed (non-fatal): $($_.Exception.Message)"
    }
  } else {
    Write-Ok ("Memory core path: {0}" -f $memoryCorePath)
  }
}

# --- Run Ester entrypoint ---
$entry = Join-Path $root $EntryScript
if (-not (Test-Path $entry)) {
  Write-Err "Entrypoint not found: $entry"
  exit 2
}

# ВАЖНО: в PowerShell конструкция $var:$x парсится как "namespace", поэтому используем $() для склейки.
Write-Ok ("Starting {0} on {1}:{2} ..." -f $EntryScript, $HostIP, $Port)

# -X utf8: force UTF-8 mode inside Python (belt + suspenders)
if ((Test-Path $venvRoot) -and (Test-Path $bootstrap)) {
  & $pythonExe -S -X utf8 $bootstrap $EntryScript
} else {
  & $pythonExe -X utf8 $entry
}
