# venv_guard.ps1  — activate venv and load .env into current process (ASCII only)
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\venv_guard.ps1 -AutoFix -LoadEnv -EnvPath ".env"
#   or set $env:DOTENV_FILE=".env.restored" and run with -LoadEnv
param(
    [switch]$AutoFix,
    [switch]$LoadEnv,
    [string]$EnvPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log([string]$lvl,[string]$msg){ Write-Host ("[{0}] {1}" -f $lvl, $msg) }
function Ok([string]$m){ Log "ok" $m }
function Info([string]$m){ Log "info" $m }
function Warn([string]$m){ Log "warn" $m }
function Fail([string]$m){ throw $m }

# ---------- 1) Ensure venv ----------
$repo = (Get-Location).Path
$venvPython = Join-Path $repo ".venv\Scripts\python.exe"
$venvActivate = Join-Path $repo ".venv\Scripts\Activate.ps1"

if (-not (Test-Path $venvPython)) {
    if ($AutoFix) {
        Info "No .venv found. Creating..."
        if (Get-Command py -ErrorAction SilentlyContinue) {
            py -3 -m venv (Join-Path $repo ".venv") | Out-Null
        } else {
            python -m venv (Join-Path $repo ".venv") | Out-Null
        }
    } else {
        Warn ".venv not found. Run with -AutoFix to create."
    }
}

if (Test-Path $venvActivate) {
    . $venvActivate
    if (Test-Path $venvPython) {
        Ok ("venv activated: {0}" -f $venvPython)
    } else {
        Warn "venv activate ran, but python.exe missing"
    }
} else {
    Warn "Activate.ps1 not found. Skip activation."
}

# ---------- 2) Resolve .env ----------
function Resolve-EnvFile {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    if ($env:DOTENV_FILE) { $candidates += $env:DOTENV_FILE }
    $candidates += ".env.local", ".env", ".env.restored"

    foreach ($p in $candidates) {
        $abs = if ([System.IO.Path]::IsPathRooted($p)) { $p } else { Join-Path $repo $p }
        if (Test-Path $abs) { return $abs }
    }
    return $null
}

# ---------- 3) Load .env into Process ----------
function Unquote([string]$s){
    if ($null -eq $s) { return "" }
    $t = $s.Trim()
    if (($t.StartsWith('"') -and $t.EndsWith('"')) -or ($t.StartsWith("'") -and $t.EndsWith("'"))) {
        $t = $t.Substring(1, $t.Length-2)
    }
    $t = $t -replace "\\n","`n" -replace "\\r","`r" -replace "\\t","`t"
    return $t
}

function Set-ProcEnv([string]$k,[string]$v){
    # process-level only; avoids registry edits
    [Environment]::SetEnvironmentVariable($k,$v,'Process')
    Set-Item -Path Env:$k -Value $v | Out-Null
}

function Parse-And-Load([string]$envFile){
    Info ("Loading ENV from: {0}" -f $envFile)
    $raw = Get-Content -LiteralPath $envFile -Raw -Encoding UTF8

    foreach ($line in ($raw -split "`n")){
        $ln = $line.Trim()
        if ($ln -eq "" -or $ln.StartsWith("#") -or $ln.StartsWith(";")) { continue }
        # support: KEY=VAL  /  export KEY=VAL
        $m = [regex]::Match($ln, '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$')
        if (-not $m.Success) { continue }
        $key = $m.Groups[1].Value
        $val = Unquote($m.Groups[2].Value)

        Set-ProcEnv $key $val
    }

    # ----- Bridges (explicit + hidden) -----
    # explicit: bridge OpenAI-style and LM Studio style bases
    if ($env:OPENAI_API_BASE -and -not $env:LMSTUDIO_URL) { Set-ProcEnv "LMSTUDIO_URL" $env:OPENAI_API_BASE }
    if ($env:LMSTUDIO_URL -and -not $env:OPENAI_API_BASE) { Set-ProcEnv "OPENAI_API_BASE" $env:LMSTUDIO_URL }

    # hidden #1: embeddings alias
    if ($env:EMBED_MODEL -and -not $env:EMBEDDINGS_MODEL) { Set-ProcEnv "EMBEDDINGS_MODEL" $env:EMBED_MODEL }
    # hidden #2: default data root
    if (-not $env:ESTER_DATA_ROOT) { Set-ProcEnv "ESTER_DATA_ROOT" (Join-Path $repo "data") }
    # hidden #3: AB safety default
    if (-not $env:AB_MODE) { Set-ProcEnv "AB_MODE" "B" }
}

if ($LoadEnv) {
    $envFile = Resolve-EnvFile -Explicit $EnvPath
    if (-not $envFile) { Fail "No .env found (tried: -EnvPath, DOTENV_FILE, .env.local, .env, .env.restored)" }
    Parse-And-Load -envFile $envFile
}

# ---------- 4) Print summary ----------
$keys = @(
    "ESTER_DATA_ROOT","PERSIST_DIR",
    "OPENAI_API_BASE","LMSTUDIO_URL",
    "OPENAI_API_KEY","EMBED_MODEL","EMBEDDINGS_MODEL","EMBED_DIM","AB_MODE"
)
foreach ($k in $keys) {
    $v = [Environment]::GetEnvironmentVariable($k,'Process')
    if ($null -eq $v -or $v -eq "") { $v = "(empty)" }
    Write-Host ("{0}={1}" -f $k,$v)
}

Ok "done"