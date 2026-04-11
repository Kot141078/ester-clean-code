param(
  [string]$ProjectRoot = "<repo-root>",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ==============================
# Ester patch B5: fix WHOIS regex mojibake + guard arbitrage in TG handler (PS5-safe)
#
# Explicit bridge: c=a+b -> (a) polzovatelskiy tekst na russkom + (b) protsedurnye guards (encoding-safe regex + try/except)
#                   => (c) a stable communication channel without crashes.
# Hidden bridges:
#  - Enderton (logic): “I do not allow conclusions from contradictory premises” -> regex should not destroy the interpreter.
#  - Carpet&Thomas (channel): protection against "decoding error" as from degradation of the transmission channel.
#  - Ashby (cybernetics): added boil (insurance) so that the system survives in a greater number of states.
# Erth (engineering/anatomy): like a ligament/suture - it’s better to put a ligature (tri/except) and replace a crooked vessel (regex),
#                              than to lose the entire blood supply (TG handler) because of one “broken” line.
# ==============================

function Write-Utf8NoBom([string]$Path, [string]$Content) {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

$run = Join-Path $ProjectRoot "run_ester_fixed.py"
if (!(Test-Path $run)) { throw "Not found: $run" }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$run.bak_$ts"
Copy-Item $run $bak -Force
Write-Host "Backup: $bak"

# Read as UTF-8 bytes (best effort; even if file already mojibake, we'll overwrite critical parts safely)
$bytes = [System.IO.File]::ReadAllBytes($run)
$src   = [System.Text.Encoding]::UTF8.GetString($bytes)

# --- Patch 1: replace whole _is_whois_query(...) with ASCII-only regex via \uXXXX escapes (encoding-safe)
$patWhois = "(?s)def _is_whois_query\([^\)]*\)\s*->\s*Optional\[str\]\s*:\s*\n.*?\n(?=\s*# --- 7\))"

$replacementWhois = @"
def _is_whois_query(text: str) -> Optional[str]:
    """Encoding-safe detector for queries like 'kto takoy <Imya>'.

    Important: uses only ASCII in the regex (via \uXXXX escapes) to avoid source-encoding corruption.
    Never raises; returns extracted name or None.
    """
    try:
        s = (text or "").strip()
        if not s:
            return None

        # who (such|such|this) <Name?>b
        # Cyrillic range: \u0400-\u04FF (covers Russian + extended Cyrillic).
        pat = (
            r"(?i)\b(?:\u043a\u0442\u043e)\s+"
            r"(?:\u0442\u0430\u043a\u043e\u0439|\u0442\u0430\u043a\u0430\u044f|\u044d\u0442\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        m = re.search(pat, s)
        if not m:
            return None

        name = (m.group(1) or "").strip()
        name = re.sub(r"\s{2,}", " ", name)
        return name if len(name) >= 2 else None
    except Exception:
        return None

"@

$rxOpt = [System.Text.RegularExpressions.RegexOptions]::Singleline
$rxWhois = New-Object System.Text.RegularExpressions.Regex($patWhois, $rxOpt)

if (-not $rxWhois.IsMatch($src)) {
  throw "Patch1 failed: cannot locate _is_whois_query(...) block (expected marker '# --- 7)')."
}
$src2 = $rxWhois.Replace($src, $replacementWhois, 1)
Write-Host "[patch] _is_whois_query: replaced with encoding-safe version"

# --- Patch 2: wrap fallback arbitrage call in handle_message with try/except (so TG never dies)
$patArb = "(?s)(\n\s*# 2\) Fallback to Arbitrage\s*\n\s*if not answer_text:\s*\n)(\s*answer_text = await ester_arbitrage\(\s*\n.*?\n\s*\)\s*\n)"
$rxArb  = New-Object System.Text.RegularExpressions.Regex($patArb, $rxOpt)

if (-not $rxArb.IsMatch($src2)) {
  throw "Patch2 failed: cannot locate 'Fallback to Arbitrage' block in handle_message."
}

# Indent helper: add 4 spaces to each non-empty line of the captured call block
function Indent-Block([string]$block, [int]$n) {
  $prefix = (" " * $n)
  $lines = $block -split "`n", -1
  $out = New-Object System.Collections.Generic.List[string]
  foreach ($ln in $lines) {
    if ($ln.Trim().Length -gt 0) { $out.Add($prefix + $ln) } else { $out.Add($ln) }
  }
  return ($out -join "`n")
}

$src3 = $rxArb.Replace($src2, {
  param($m)
  $head = $m.Groups[1].Value
  $call = $m.Groups[2].Value
  $callIndented = Indent-Block $call 4  # inside try:
  return $head +
"        try:
" + $callIndented + "
        except Exception as e:
            logging.getLogger(__name__).exception('[ARBITRAGE] unhandled error: %s', e)
            answer_text = 'Vnutrennyaya oshibka. Sm. log [ARBITRAGE].'
"
}, 1)

Write-Host "[patch] handle_message: arbitrage guarded with try/except"

if ($DryRun) {
  Write-Host "[dryrun] not writing changes"
  exit 0
}

Write-Utf8NoBom -Path $run -Content $src3
Write-Host "[OK] B5 applied: $run"

# --- Smoke: compile the exact regex pattern we inject (sanity)
$py = @"
import re
pat = (
  r"(?i)\b(?:\u043a\u0442\u043e)\s+"
  r"(?:\u0442\u0430\u043a\u043e\u0439|\u0442\u0430\u043a\u0430\u044f|\u044d\u0442\u043e)\s+"
  r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
)
re.compile(pat)
print("smoke: whois regex compile OK")
m = re.search(pat, "kto takoy Pushkin?")
print("smoke: match =", m.group(1) if m else None)
"@

# run smoke with SAME python you use to start ester (python in PATH)
Write-Host "[smoke] python (PATH) regex compile test"
$py | python

Write-Host "Done."
Write-Host "Tip: to run Ester with venv, use:"
Write-Host "  .\.venv\Scripts\python.exe run_ester_fixed.py"
