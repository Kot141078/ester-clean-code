<#
Ester patch B3 (PS5-safe): Web bridge diagnostics + Analyst sync + DDGS hardening.

Explicit bridge (c=a+b): user request (a) + deterministic web bridge + compatibility shim (b) => verifiable answer (c)
Hidden bridges:
  - Ashby: requisite variety via provider fallback + relevance filtering
  - Cover&Thomas: channel capacity -> drop noisy / off-topic packets instead of decoding garbage
  - Gray's: "tendon shim" between modules (read_text hook -> analyst) to prevent disconnection
Earth (engineering/anatomy):
  A sensor that sometimes returns random noise must be fused with a gate, not "trusted harder".
  Like proprioception: if the signal is inconsistent, the reflex should inhibit movement, not guess a position.
#>

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [switch]$InstallDDGS
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info([string]$m) { Write-Host $m -ForegroundColor Cyan }
function Warn([string]$m) { Write-Host $m -ForegroundColor Yellow }
function Die([string]$m)  { throw $m }

function WriteUtf8Bom([string]$Path, [string]$Content) {
  $enc = New-Object System.Text.UTF8Encoding($true) # BOM = true
  [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function ReadText([string]$Path) {
  return [System.IO.File]::ReadAllText($Path)
}

function BackupFile([string]$Path) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $bak = "$Path.bak_$ts"
  Copy-Item -LiteralPath $Path -Destination $bak -Force
  return $bak
}

function TryInstallDDGS([string]$ProjRoot) {
  $py = Join-Path $ProjRoot ".\.venv\Scripts\python.exe"
  if (!(Test-Path $py)) { Die "python venv not found: $py" }

  Info "[pip] Installing ddgs (preferred). If it fails, falling back to duckduckgo-search..."
  $ok = $true
  try {
    & $py -m pip install -U ddgs | Out-Host
  } catch {
    $ok = $false
  }

  if (-not $ok) {
    Warn "[pip] ddgs install failed. Installing duckduckgo-search instead..."
    & $py -m pip install -U duckduckgo-search | Out-Host
  }
}

function RegexReplaceOnce([string]$Text, [string]$Pattern, [string]$Replacement) {
  $rx = New-Object System.Text.RegularExpressions.Regex($Pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
  if (-not $rx.IsMatch($Text)) { return $Text }
  return $rx.Replace($Text, $Replacement, 1)
}

function EnsureAnalystShim([string]$Path) {
  $txt = ReadText $Path
  $orig = $txt

  if ($txt -notmatch "def\s+process_incoming_data\s*\(") {
    Info "[patch] analyst.py: adding process_incoming_data shim"
    $insert = @"
    def process_incoming_data(self, payload):
        """Compatibility shim for bridges.internet_access.read_text hook."""
        try:
            self.submit_event("internet_access", payload)
        except Exception as e:
            logger.error(f"[ANALYST] process_incoming_data failed: {e}")

"@
    # insert right before global instance creation (keeps indentation inside class)
    $txt = RegexReplaceOnce $txt '(?m)^\s*analyst\s*=\s*EsterAnalyst\(\)\s*$' ($insert + "analyst = EsterAnalyst()")
  }

  if ($txt -match '(?m)^\s*analyst\s*=\s*EsterAnalyst\(\)\s*$' -and $txt -notmatch '(?m)^\s*analyst_unit\s*=\s*analyst\s*$') {
    Info "[patch] analyst.py: adding analyst_unit alias"
    $txt = $txt -replace '(?m)^\s*analyst\s*=\s*EsterAnalyst\(\)\s*$',"analyst = EsterAnalyst()`nanalyst_unit = analyst"
  }

  if ($txt -ne $orig) {
    WriteUtf8Bom $Path $txt
  }
}

function EnsureInternetAccessHardening([string]$Path) {
  $txt = ReadText $Path
  $orig = $txt

  if ($txt -notmatch 'DDGS_REGION') {
    Info "[patch] internet_access.py: prefer ddgs import + add region/safesearch/timelimit + relevance filter"

    # 1) Replace "from duckduckgo_search import DDGS" inside _search_ddgs with try-import ddgs
    $rxImp = New-Object System.Text.RegularExpressions.Regex('(?m)^(\s*)from\s+duckduckgo_search\s+import\s+DDGS\s*$')
    if ($rxImp.IsMatch($txt)) {
      $txt = $rxImp.Replace($txt, {
        param($m)
        $i = $m.Groups[1].Value
        return @"
${i}try:
${i}    from ddgs import DDGS  # preferred: pip install ddgs
${i}except Exception:
${i}    from duckduckgo_search import DDGS  # legacy: pip install duckduckgo-search
"@
      }, 1)
    }

    # 2) Replace ddgs.text call to pass env-controlled params (with TypeError fallback)
    $rxCall = New-Object System.Text.RegularExpressions.Regex('(?m)^(\s*)results\s*=\s*ddgs\.text\(query,\s*max_results=max_results\)\s*$')
    if ($rxCall.IsMatch($txt)) {
      $txt = $rxCall.Replace($txt, {
        param($m)
        $i = $m.Groups[1].Value
        return @"
${i}region = os.getenv("DDGS_REGION", "us-en")
${i}safesearch = os.getenv("DDGS_SAFESEARCH", "off")
${i}timelimit = os.getenv("DDGS_TIMELIMIT", "w")  # d/w/m/y or empty/None
${i}try:
${i}    results = ddgs.text(query, region=region, safesearch=safesearch, timelimit=timelimit, max_results=max_results)
${i}except TypeError:
${i}    results = ddgs.text(query, max_results=max_results)
"@
      }, 1)
    }

    # 3) Inject relevance filter right before "if not results:" in _search_ddgs
    $rxIfEmpty = New-Object System.Text.RegularExpressions.Regex('(?m)^(\s*)if\s+not\s+results\s*:\s*$')
    if ($rxIfEmpty.IsMatch($txt) -and $txt -notmatch 'relevance filter') {
      $txt = $rxIfEmpty.Replace($txt, {
        param($m)
        $i = $m.Groups[1].Value
        return @"
${i}# relevance filter: drop off-topic noise instead of feeding hallucinations
${i}try:
${i}    import re as _re
${i}    _q = (query or "").lower()
${i}    _stop = set(["latest","stable","current","price","version","now","today","what","who","the","is","of","in","on","at","as"])
${i}    _tokens = [t for t in _re.findall(r"[a-z0-9]{3,}|[a-ya0-9]{3,}", _q) if t not in _stop]
${i}    if _tokens:
${i}        _f = []
${i}        for _r in results:
${i}            _blob = (str(_r.get("title","")) + " " + str(_r.get("body","")) + " " + str(_r.get("href",""))).lower()
${i}            if any(t in _blob for t in _tokens):
${i}                _f.append(_r)
${i}        results = _f
${i}except Exception:
${i}    pass

${i}if not results:
"@
      }, 1)
    }
  }

  if ($txt -ne $orig) {
    WriteUtf8Bom $Path $txt
  }
}

# --- MAIN ---
$proj = (Resolve-Path -LiteralPath $ProjectRoot).Path
Info "ProjectRoot: $proj"

if ($InstallDDGS) { TryInstallDDGS $proj }

$ia = Join-Path $proj "bridges\internet_access.py"
$an = Join-Path $proj "modules\analyst.py"

if (!(Test-Path $ia)) { Die "Missing file: $ia" }
if (!(Test-Path $an)) { Die "Missing file: $an" }

$b1 = BackupFile $ia
$b2 = BackupFile $an
Info "Backups:"
Info "  $b1"
Info "  $b2"

try {
  EnsureAnalystShim $an
  EnsureInternetAccessHardening $ia
  Info "[OK] Patch applied."
} catch {
  Warn "[FAIL] Patch failed. Rolling back..."
  Copy-Item -LiteralPath $b1 -Destination $ia -Force
  Copy-Item -LiteralPath $b2 -Destination $an -Force
  throw
}

Info "Done."
Info "Tip: set env for stability:"
Info "  `$env:DDGS_REGION='us-en' ; `$env:DDGS_TIMELIMIT='w' ; `$env:DDGS_SAFESEARCH='off'"
