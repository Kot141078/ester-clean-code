# logscan_pow.ps1 (v2.1)
# ASCII-only PowerShell wrapper for Python log scanner
# Fix for Windows PowerShell 5.1: no ProcessStartInfo.ArgumentList
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass `
#     -File .\tools\logscan_pow.ps1 `
#     -LogPath "<repo-root>\Log.txt" `
#     -OutDir ".\out_log"

param(
    [Parameter(Mandatory=$true)]
    [string]$LogPath,
    [Parameter(Mandatory=$true)]
    [string]$OutDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    [Console]::InputEncoding  = New-Object System.Text.UTF8Encoding($false)
} catch {}

# Resolve paths
$cwd = (Get-Location).Path
if (-not [System.IO.Path]::IsPathRooted($LogPath)) {
    $LogPath = [System.IO.Path]::GetFullPath((Join-Path $cwd $LogPath))
}
if (-not [System.IO.Path]::IsPathRooted($OutDir)) {
    $OutDir = [System.IO.Path]::GetFullPath((Join-Path $cwd $OutDir))
}

function Die([string]$msg) {
    Write-Error $msg
    exit 1
}

if (-not (Test-Path -LiteralPath $LogPath)) {
    Die ("File not found: {0}" -f $LogPath)
}

# Ensure out dir
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Pick python (preferring current session venv)
$pythonExe = $null
try { $pythonExe = (Get-Command python -ErrorAction Stop).Source } catch {
    try { $pythonExe = (Get-Command py -ErrorAction Stop).Source } catch {}
}
if (-not $pythonExe) { Die "Python not found in PATH. Activate your venv first." }

# Compute script path next to this ps1
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Path
$pyScript = Join-Path $scriptDir "logscan_py.py"
if (-not (Test-Path -LiteralPath $pyScript)) {
    Die ("Python script not found: {0}" -f $pyScript)
}

Write-Host ("Running analyzer: {0}" -f $pyScript)

# Call Python via PowerShell invocation operator to keep PS5.1 compatible
# Capture stdout+stderr and exit code
$allOutput = & $pythonExe $pyScript --log $LogPath --out $OutDir 2>&1
$exitCode = $LASTEXITCODE

if ($allOutput) {
    # Print as plain text
    $allOutput | ForEach-Object {
        if ($_ -ne $null) { Write-Host ($_ | Out-String).Trim() }
    }
}

if (-not $exitCode) { $exitCode = 0 }  # normalize $null to 0
if ($exitCode -ne 0) {
    Die ("Analyzer failed with exit code {0}" -f $exitCode)
}

Write-Host ("Done. Reports at: {0}" -f $OutDir)
exit 0
