#requires -Version 5.1
<#
Sister AutoChat patcher for run_ester_fixed.py

YaVNYY MOST: c=a+b -> patch (a) + proverka/rollback (b) => stabilnoe izmenenie (c).
SKRYTYE MOSTY:
  - Ashby: umenshaem raznoobrazie oshibok cherez determinirovannye yakorya + idempotentnost.
  - Cover&Thomas: kontrol shuma — patchim tolko 3 tochki, bez “perepisyvaniya fayla”.
ZEMNOY ABZATs: kak predokhranitel v schitke — snachala backup, potom vmeshatelstvo, inache avto-otkat.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Path = "D:\ester-project\run_ester_fixed.py"
if (-not (Test-Path $Path)) { throw "Net fayla: $Path" }

# --- read as UTF-8 (bez plyasok s kodirovkoy) ---
$utf8 = New-Object System.Text.UTF8Encoding($false)
$content = [System.IO.File]::ReadAllText($Path, $utf8)

# --- backup ---
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$Path.bak_$ts"
[System.IO.File]::WriteAllText($bak, $content, $utf8)
Write-Host "OK: backup -> $bak"

function Assert-Contains([string]$Text, [string]$Needle, [string]$What) {
    if ($Text.IndexOf($Needle, [System.StringComparison]::Ordinal) -lt 0) {
        throw "Proverka ne proshla: ne naydeno '$What' ($Needle)"
    }
}

# ---------- 1) INSERT IMPORT ----------
$importNeedle = "from modules.sister_autochat import start_sister_autochat_background"
if ($content -notmatch [regex]::Escape($importNeedle)) {
    $anchor = "from modules.analyst import analyst"
    if ($content -notmatch [regex]::Escape($anchor)) { throw "Ne nayden anchor importa: $anchor" }

    $importBlock = @"
$anchor

# --- Sister AutoChat (import) ---
try:
    from modules.sister_autochat import start_sister_autochat_background
except Exception:
    start_sister_autochat_background = lambda: None  # soft disabled

"@

    # zamenyaem rovno odin raz
    $content = $content -replace [regex]::Escape($anchor), [System.Text.RegularExpressions.Regex]::Escape($anchor)  # no-op safeguard
    # normalnaya zamena:
    $content = $content -replace [regex]::Escape($anchor), ($importBlock -replace "\$anchor",$anchor)
    Write-Host "OK: inserted import block"
} else {
    Write-Host "SKIP: import already present"
}

# ---------- 2) START AUTOCHAT IN __main__ ----------
$startTag = "AUTOCHAT = start_sister_autochat_background()"
if ($content -notmatch [regex]::Escape($startTag)) {
    $threadLine = "threading.Thread(target=run_flask_background, daemon=True).start()"
    if ($content -notmatch [regex]::Escape($threadLine)) { throw "Ne nayden anchor __main__: $threadLine" }

    # insert flask threads immediately after the start line (with the same indentation)
    $pattern = "(?m)^(?<indent>\s*)$([regex]::Escape($threadLine))\s*$"
    $repl = '${indent}' + $threadLine + "`r`n`r`n" +
            '${indent}' + "# --- Sister AutoChat (background) ---`r`n" +
            '${indent}' + "AUTOCHAT = start_sister_autochat_background()`r`n"

    $new = [regex]::Replace($content, $pattern, $repl, 1)
    if ($new -eq $content) { throw "Ne udalos vstavit zapusk AutoChat v __main__ (pattern mismatch)" }
    $content = $new
    Write-Host "OK: inserted autochat start"
} else {
    Write-Host "SKIP: autochat start already present"
}

# ---------- 3) MARK USER ACTIVITY IN handle_message ----------
$markNeedle = "AUTOCHAT.mark_user_activity()"
if ($content -notmatch [regex]::Escape($markNeedle)) {
    # We insert it only in the handle_message, after the block:
    # text = (msg.text or "").strip()
    # if not text:
    #     return
    $pattern = "(?s)(async def handle_message\(.*?\n\s*text\s*=\s*\(msg\.text\s*or\s*\"\"\)\.strip\(\)\s*\n\s*if\s+not\s+text:\s*\n\s*return\s*\n)"
    $insert = @"
`$1
    # --- Sister AutoChat: user activity (idle gate) ---
    try:
        if "AUTOCHAT" in globals() and AUTOCHAT:
            AUTOCHAT.mark_user_activity()
    except Exception:
        pass

"@
    $new = [regex]::Replace($content, $pattern, $insert, 1)
    if ($new -eq $content) { throw "Ne udalos vstavit mark_user_activity v handle_message (pattern mismatch)" }
    $content = $new
    Write-Host "OK: inserted mark_user_activity"
} else {
    Write-Host "SKIP: mark_user_activity already present"
}

# ---------- VERIFY ----------
try {
    Assert-Contains $content "modules.sister_autochat" "import modules.sister_autochat"
    Assert-Contains $content "AUTOCHAT = start_sister_autochat_background()" "autochat start"
    Assert-Contains $content "AUTOCHAT.mark_user_activity()" "mark_user_activity"
} catch {
    Write-Host "FAIL: verify -> rollback" -ForegroundColor Red
    [System.IO.File]::WriteAllText($Path, [System.IO.File]::ReadAllText($bak, $utf8), $utf8)
    throw
}

# ---------- WRITE ----------
[System.IO.File]::WriteAllText($Path, $content, $utf8)
Write-Host "OK: patched -> $Path"