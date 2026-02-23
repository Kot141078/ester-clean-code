#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "D:\ester-project"
$PyPath      = Join-Path $ProjectRoot "run_ester_fixed.py"

function Read-Text([string]$Path) {
    $sr = New-Object System.IO.StreamReader($Path, [System.Text.Encoding]::UTF8, $true)
    try { return $sr.ReadToEnd() } finally { $sr.Close() }
}

function Write-Text([string]$Path, [string]$Text) {
    $enc = New-Object System.Text.UTF8Encoding($true)  # UTF-8 with BOM (stable for PS5)
    $sw  = New-Object System.IO.StreamWriter($Path, $false, $enc)
    try { $sw.Write($Text) } finally { $sw.Close() }
}

function Backup-File([string]$Path, [string]$Content) {
    $ts  = Get-Date -Format "yyyyMMdd_HHmmss"
    $bak = "$Path.bak_$ts"
    Write-Text $bak $Content
    Write-Host ("OK: backup -> " + $bak)
}

if (-not (Test-Path $PyPath)) { throw ("No file: " + $PyPath) }

$content = Read-Text $PyPath
Backup-File $PyPath $content

# normalize to LF for patching
$t = $content -replace "`r`n", "`n"

$tagImport = "# --- Sister AutoChat (import) ---"
$tagStart  = "# --- Sister AutoChat (background) ---"
$tagMark   = "# --- Sister AutoChat: user activity (idle gate) ---"

# 1) import block after: from modules.analyst import analyst
if ($t -notmatch [regex]::Escape($tagImport)) {
    $anchor = "from modules.analyst import analyst"
    $idx = $t.IndexOf($anchor)
    if ($idx -lt 0) { throw ("Anchor not found: " + $anchor) }

    $eol = $t.IndexOf("`n", $idx)
    if ($eol -lt 0) { $insertPos = $t.Length } else { $insertPos = $eol + 1 }

    $ins = @(
        $tagImport
        "try:"
        "    from modules.sister_autochat import start_sister_autochat_background"
        "except Exception:"
        "    start_sister_autochat_background = lambda: None  # soft-disabled"
        ""
    ) -join "`n"

    $t = $t.Insert($insertPos, $ins + "`n")
    Write-Host "OK: inserted import block"
} else {
    Write-Host "SKIP: import block already present"
}

# 2) start autochat in __main__ right after Flask background thread start
if ($t -notmatch [regex]::Escape($tagStart)) {
    $threadLine = "threading.Thread(target=run_flask_background, daemon=True).start()"
    $idx = $t.IndexOf($threadLine)
    if ($idx -lt 0) { throw ("Anchor not found: " + $threadLine) }

    $lineStart = $t.LastIndexOf("`n", $idx)
    if ($lineStart -lt 0) { $lineStart = 0 } else { $lineStart += 1 }

    $lineEnd = $t.IndexOf("`n", $idx)
    if ($lineEnd -lt 0) { $lineEnd = $t.Length }

    $line = $t.Substring($lineStart, $lineEnd - $lineStart)
    $m = [regex]::Match($line, '^(?<indent>\s*)')
    $indent = $m.Groups["indent"].Value

    $ins = @(
        $indent + $tagStart
        $indent + "AUTOCHAT = start_sister_autochat_background()"
        ""
    ) -join "`n"

    $insertPos = if ($lineEnd -ge $t.Length) { $t.Length } else { $lineEnd + 1 }
    $t = $t.Insert($insertPos, $ins + "`n")
    Write-Host "OK: inserted autochat start"
} else {
    Write-Host "SKIP: autochat start already present"
}

# 3) mark_user_activity inside handle_message after:
# text = (msg.text or "").strip()
# if not text:
#     return
if ($t -notmatch [regex]::Escape($tagMark)) {
    $lines = $t -split "`n", 0
    $out = New-Object System.Collections.Generic.List[string]
    $inHandle = $false
    $inserted = $false

    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]

        if ($line -match '^async def handle_message\(') { $inHandle = $true }
        elseif ($inHandle -and $line -match '^async def ') { $inHandle = $false }

        $out.Add($line)

        if ($inHandle -and -not $inserted) {
            if ($line.TrimEnd() -eq 'return' -and $i -ge 2) {
                if ($lines[$i-1].TrimEnd() -eq 'if not text:' -and $lines[$i-2].TrimEnd() -eq 'text = (msg.text or "").strip()') {
                    $out.Add("")
                    $out.Add("    " + $tagMark)
                    $out.Add("    try:")
                    $out.Add('        if "AUTOCHAT" in globals() and AUTOCHAT:')
                    $out.Add("            AUTOCHAT.mark_user_activity()")
                    $out.Add("    except Exception:")
                    $out.Add("        pass")
                    $out.Add("")
                    $inserted = $true
                }
            }
        }
    }

    if (-not $inserted) { throw "Failed to locate insertion point in handle_message" }

    $t = ($out -join "`n")
    Write-Host "OK: inserted mark_user_activity"
} else {
    Write-Host "SKIP: mark_user_activity already present"
}

# verify
foreach ($needle in @($tagImport, $tagStart, $tagMark)) {
    if ($t -notmatch [regex]::Escape($needle)) { throw ("Verify failed: " + $needle) }
}

# write back as CRLF
$outText = $t -replace "`n", "`r`n"
Write-Text $PyPath $outText

Write-Host ("OK: patched -> " + $PyPath)
