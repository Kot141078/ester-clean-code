# apply_patch_20251227_ctxq.ps1
# PowerShell 5.1 safe (ASCII only). Writes module from Base64 as UTF-8 bytes.
# Auto-rollback on any failure.

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-Timestamp {
    return (Get-Date).ToString("yyyyMMdd_HHmmss")
}

function Read-TextAuto([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)

    # Try UTF-8 first
    $utf8 = New-Object System.Text.UTF8Encoding($false, $true)
    try {
        $text = $utf8.GetString($bytes)
        # If it contains many replacement chars, fallback to CP1251
        $repCount = ([regex]::Matches($text, "�")).Count
        if ($repCount -gt 10) { throw "Too many replacement chars" }
        return $text
    } catch {
        $cp1251 = [System.Text.Encoding]::GetEncoding(1251)
        return $cp1251.GetString($bytes)
    }
}

function Write-Utf8NoBom([string]$Path, [string]$Text) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $bytes = $utf8.GetBytes($Text)
    [System.IO.File]::WriteAllBytes($Path, $bytes)
}

function Write-Bytes([string]$Path, [byte[]]$Bytes) {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    [System.IO.File]::WriteAllBytes($Path, $Bytes)
}

function Insert-AfterLineOnce([string]$Text, [string]$NeedleLineRegex, [string]$Block, [string]$Marker) {
    if ($Text -match [regex]::Escape($Marker)) { return $Text }

    $rx = New-Object System.Text.RegularExpressions.Regex($NeedleLineRegex, [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if (-not $rx.IsMatch($Text)) { throw "Anchor not found for marker: $Marker" }

    $evaluator = {
        param($m)
        return $m.Value + "`r`n" + $Block
    }

    return $rx.Replace($Text, $evaluator, 1)
}

function Insert-AfterAskIvanOnce([string]$Text) {
    if ($Text -match "\[CTXQ PATCH ASK START\]") { return $Text }

    $rx = New-Object System.Text.RegularExpressions.Regex('(?m)^(?<indent>[ \t]*)if\s+tag\s*==\s*["'']ASK_OWNER["'']:\s*\r?$', [System.Text.RegularExpressions.RegexOptions]::Multiline)
    if (-not $rx.IsMatch($Text)) { throw "ASK_OWNER anchor not found" }

    $evaluator = {
        param($m)
        $indent = $m.Groups["indent"].Value
        $inner = $indent + "    "

        $block = @"
$inner# [CTXQ PATCH ASK START]
$innerif ('_CTXQ_ENGINE' -in (Get-Variable -Scope Global | ForEach-Object { $_.Name }) ) { }
$innerif ((Get-Variable -Name _CTXQ_ENGINE -Scope Global -ErrorAction SilentlyContinue) -and ($global:_CTXQ_ENGINE -ne $null)) {
$inner    try {
$inner        $uname = $null
$inner        try { $uname = (Get-Variable -Name OWNER_NAME -Scope Global -ErrorAction SilentlyContinue).Value } catch { }
$inner        if (-not $uname) { try { $uname = (Get-Variable -Name ADMIN_NAME -Scope Global -ErrorAction SilentlyContinue).Value } catch { } }
$inner        if (-not $uname) { $uname = "Owner" }
$inner        payload = $global:_CTXQ_ENGINE.suggest_question(
$inner            default_question = payload,
$inner            user_name        = [string]$uname,
$inner            mem_text         = mem,
$inner            draft_text       = draft
$inner        ).strip()
$inner    } catch {
$inner        try { logging.warning("[CTXQ] suggest failed: " + $_.Exception.Message) } catch { }
$inner    }
$inner}
$inner# [CTXQ PATCH ASK END]
"@

        return $m.Value + "`r`n" + $block
    }

    return $rx.Replace($Text, $evaluator, 1)
}

# --- Paths ---
$ProjectDir = (Get-Location).Path
$RunnerPath = Join-Path $ProjectDir "run_ester_fixed.py"
$ModulePath = Join-Path $ProjectDir "modules\context_question_engine.py"

if (-not (Test-Path $RunnerPath)) { throw "run_ester_fixed.py not found in: $ProjectDir" }

$ts = Get-Timestamp
$BackupRunner = "$RunnerPath.bak_$ts"
$BackupModule = "$ModulePath.bak_$ts"

Write-Host ">>> CTXQ patch start ($ts)" -ForegroundColor Cyan
Write-Host "ProjectDir: $ProjectDir"
Write-Host "Runner:     $RunnerPath"
Write-Host "Module:     $ModulePath"

# --- Backup ---
Copy-Item -LiteralPath $RunnerPath -Destination $BackupRunner -Force
if (Test-Path $ModulePath) { Copy-Item -LiteralPath $ModulePath -Destination $BackupModule -Force }

# --- Module content (Base64 UTF-8) ---
$B64_MODULE = @'
IyAtKi0gY29kaW5nOiB1dGYtOCAtKi0KIiIiCm1vZHVsZXMvY29udGV4dF9xdWVzdGlvbl9lbmdpbmUucHkg4oCUINCa0L7QvdGC0LXQutGB0YLQvdGL0Lkg0LTQstC40LbQvtC6INCy0L7Qv9GA0L7RgdC+0LIgKENUWFEpCgp... (TRUNCATED IN THIS VIEW) ...
'@

try {
    # Write module bytes
    $modBytes = [System.Convert]::FromBase64String($B64_MODULE)
    Write-Bytes -Path $ModulePath -Bytes $modBytes
    Write-Host "OK: module written." -ForegroundColor Green

    # Read & patch runner
    $txt = Read-TextAuto -Path $RunnerPath

    # 1) imports
    $importBlock = @"
# [CTXQ PATCH IMPORTS START]
try:
    from modules.context_question_engine import ContextQuestionEngine  # noqa: F401
except Exception:
    ContextQuestionEngine = None  # type: ignore
# [CTXQ PATCH IMPORTS END]
"@

    $txt = Insert-AfterLineOnce -Text $txt `
        -NeedleLineRegex '(?m)^import\s+logging\s*$' `
        -Block $importBlock `
        -Marker '# [CTXQ PATCH IMPORTS START]'

    # 2) engine init (after hive = EsterHiveMind())
    $engineBlock = @"
# [CTXQ PATCH ENGINE START]
_CTXQ_ENGINE = None
if 'ContextQuestionEngine' in globals() and ContextQuestionEngine is not None:
    try:
        _CTXQ_ROOT = globals().get("PROJECT_DIR") or globals().get("ESTER_HOME") or os.getcwd()
        _CTXQ_ENGINE = ContextQuestionEngine(project_root=str(_CTXQ_ROOT), memory_file=MEMORY_FILE)
        logging.info("[CTXQ] ContextQuestionEngine enabled.")
    except Exception as _e:
        logging.warning(f"[CTXQ] disabled: {_e}")
        _CTXQ_ENGINE = None
# [CTXQ PATCH ENGINE END]
"@

    $txt = Insert-AfterLineOnce -Text $txt `
        -NeedleLineRegex '(?m)^hive\s*=\s*EsterHiveMind\(\)\s*$' `
        -Block $engineBlock `
        -Marker '# [CTXQ PATCH ENGINE START]'

    # 3) ASK_OWNER hook
    $txt = Insert-AfterAskIvanOnce -Text $txt

    # Write patched runner
    Write-Utf8NoBom -Path $RunnerPath -Text $txt
    Write-Host "OK: runner patched." -ForegroundColor Green

    # Compile check
    Write-Host ">>> py_compile check..." -ForegroundColor Cyan
    & python -m py_compile $RunnerPath $ModulePath
    Write-Host ">>> CTXQ PATCH OK" -ForegroundColor Green
}
catch {
    Write-Host "!!! PATCH FAILED. Rolling back..." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red

    # rollback runner
    if (Test-Path $BackupRunner) { Copy-Item -LiteralPath $BackupRunner -Destination $RunnerPath -Force }

    # rollback module
    if (Test-Path $BackupModule) {
        Copy-Item -LiteralPath $BackupModule -Destination $ModulePath -Force
    } else {
        if (Test-Path $ModulePath) { Remove-Item -LiteralPath $ModulePath -Force }
    }

    throw
}
