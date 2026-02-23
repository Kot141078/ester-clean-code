<PASTE_SCRIPT_HERE>
<#
Ester patch B4 (PS5-safe): make analyst importable without torch + force ddgs usage + fail-closed SEARCH status.

Explicit bridge (c=a+b):
  (a) "precision to the digit" requirement + (b) tooling that either returns sources or returns a hard error
  => (c) no silent hallucination when sensor is broken.

Hidden bridges:
  - Ashby: add operational variety (provider diagnostics) instead of pretending a dead sensor is alive.
  - Cover&Thomas: if the channel is down/noisy, you must surface "ERROR/EMPTY" not decode random bits as facts.
  - Gray's Anatomy: add a compatibility tendon (analyst_unit + process_incoming_data) without tearing existing tissue.

Earth (engineering/anatomy):
  If the blood pressure cuff is missing, you don't print "120/80". You print "cuff missing".
  Same here: SEARCH must fail-closed, not fail-open into fantasy.
#>

param(
  [string]$ProjectRoot = (Get-Location).Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info([string]$m) { Write-Host $m -ForegroundColor Cyan }
function Warn([string]$m) { Write-Host $m -ForegroundColor Yellow }
function Die([string]$m)  { throw $m }

function WriteUtf8Bom([string]$Path, [string]$Content) {
  $enc = New-Object System.Text.UTF8Encoding($true) # BOM
  [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function ReadAll([string]$Path) { return [System.IO.File]::ReadAllText($Path) }

function BackupFile([string]$Path) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $bak = "$Path.bak_$ts"
  Copy-Item -LiteralPath $Path -Destination $bak -Force
  return $bak
}

function ReplaceOnce([string]$Text, [string]$Pattern, [string]$Replacement) {
  $rx = New-Object System.Text.RegularExpressions.Regex($Pattern,
    [System.Text.RegularExpressions.RegexOptions]::Multiline)
  if (-not $rx.IsMatch($Text)) { return @{ Text=$Text; Changed=$false } }
  return @{ Text=$rx.Replace($Text, $Replacement, 1); Changed=$true }
}

$proj = (Resolve-Path -LiteralPath $ProjectRoot).Path
Info "ProjectRoot: $proj"

$ia = Join-Path $proj "bridges\internet_access.py"
$an = Join-Path $proj "modules\analyst.py"

if (!(Test-Path $ia)) { Die "Missing file: $ia" }
if (!(Test-Path $an)) { Die "Missing file: $an" }

$bakIa = BackupFile $ia
$bakAn = BackupFile $an
Info "Backups:"
Info "  $bakIa"
Info "  $bakAn"

try {
  # --------------------------
  # 1) modules/analyst.py: torch optional + analyst_unit + process_incoming_data shim
  # --------------------------
  $anText = ReadAll $an
  $origAn = $anText

  if ($anText -match '(?m)^\s*import\s+torch\s*$' -and $anText -notmatch 'PATCH:\s*torch optional') {
    Info "[patch] analyst.py: make torch optional"
    $block = @"
# PATCH: torch optional
try:
    import torch  # optional
except Exception as _e:
    torch = None
"@
    $anText = ($anText -replace '(?m)^\s*import\s+torch\s*$', $block)
  }

  if ($anText -notmatch 'PATCH:\s*bridge analyst_unit') {
    Info "[patch] analyst.py: add analyst_unit + process_incoming_data at module scope"
    $shim = @"

# PATCH: bridge analyst_unit
try:
    analyst_unit
except NameError:
    analyst_unit = analyst

if not hasattr(analyst_unit, "process_incoming_data"):
    def _process_incoming_data(payload):
        try:
            return analyst_unit.submit_event("internet_access", payload)
        except Exception as e:
            try:
                logger.error(f"[ANALYST] process_incoming_data failed: {e}")
            except Exception:
                pass
    analyst_unit.process_incoming_data = _process_incoming_data
"@
    $anText = $anText.TrimEnd() + $shim + "`r`n"
  }

  if ($anText -ne $origAn) {
    WriteUtf8Bom $an $anText
  } else {
    Warn "[skip] analyst.py already patched"
  }

  # --------------------------
  # 2) bridges/internet_access.py: force ddgs only, add env params, list() conversion, fail-closed message
  # --------------------------
  $iaText = ReadAll $ia
  $origIa = $iaText

  if ($iaText -notmatch 'PATCH:\s*ddgs-only') {
    Info "[patch] internet_access.py: ddgs-only import (no duckduckgo_search warning)"

    # Replace any 'from duckduckgo_search import DDGS' with ddgs-only import (keep indentation)
    $rx = New-Object System.Text.RegularExpressions.Regex('(?m)^(?<i>\s*)from\s+duckduckgo_search\s+import\s+DDGS\s*$')
    $iaText = $rx.Replace($iaText, {
      param($m)
      $i = $m.Groups["i"].Value
      return @"
${i}# PATCH: ddgs-only
${i}from ddgs import DDGS  # pip install ddgs
"@
    })

    # If file still imports DDGS from somewhere else, leave it; but ensure ddgs-only marker exists:
    $iaText = $iaText.TrimEnd() + "`r`n# PATCH: ddgs-only`r`n"
  }

  # Patch ddgs.text call: add params + list() conversion. We replace the first "results = ddgs.text(...)" line found.
  if ($iaText -notmatch 'PATCH:\s*ddgs params') {
    Info "[patch] internet_access.py: ddgs params + list() conversion"
    $rxCall = New-Object System.Text.RegularExpressions.Regex('(?m)^(?<i>\s*)results\s*=\s*ddgs\.text\([^\)]*\)\s*$')
    if ($rxCall.IsMatch($iaText)) {
      $iaText = $rxCall.Replace($iaText, {
        param($m)
        $i = $m.Groups["i"].Value
        return @"
${i}# PATCH: ddgs params
${i}region = os.getenv("DDGS_REGION", "wt-wt")
${i}safesearch = os.getenv("DDGS_SAFESEARCH", "off")
${i}timelimit = os.getenv("DDGS_TIMELIMIT", "w")
${i}try:
${i}    _it = ddgs.text(query, region=region, safesearch=safesearch, timelimit=timelimit, max_results=max_results)
${i}except TypeError:
${i}    _it = ddgs.text(query, max_results=max_results)
${i}results = list(_it) if _it is not None else []
"@
      }, 1)
    } else {
      Warn "[warn] cannot find 'results = ddgs.text(...)' line; skipping params patch"
    }
    $iaText = $iaText.TrimEnd() + "`r`n# PATCH: ddgs params`r`n"
  }

  # Patch "No relevant information..." into explicit SEARCH_EMPTY / SEARCH_ERROR markers for higher-level gating
  if ($iaText -match 'No relevant information found in the global network\.' -and $iaText -notmatch 'SEARCH_EMPTY') {
    Info "[patch] internet_access.py: fail-closed digest markers"
    $iaText = $iaText -replace 'return\s+"No relevant information found in the global network\."', 'return f"[SEARCH_EMPTY] no results for: {query}"'
  }

  if ($iaText -ne $origIa) {
    WriteUtf8Bom $ia $iaText
  } else {
    Warn "[skip] internet_access.py already patched (or patterns not found)"
  }

  Info "[OK] Patch applied."
}
catch {
  Warn "[FAIL] Patch failed. Rolling back..."
  Copy-Item -LiteralPath $bakIa -Destination $ia -Force
  Copy-Item -LiteralPath $bakAn -Destination $an -Force
  throw
}

# --------------------------
# Smoke checks
# --------------------------
$py = Join-Path $proj ".venv\Scripts\python.exe"
if (Test-Path $py) {
  Info "[smoke] import analyst_unit (should not require torch)"
  & $py -c "from modules.analyst import analyst_unit; print('analyst_unit ok:', hasattr(analyst_unit,'process_incoming_data'))"

  Info "[smoke] ddgs import (should not warn about duckduckgo_search)"
  & $py -c "from ddgs import DDGS; print('ddgs ok')"

  Info "[smoke] web digest"
  & $py -c "from bridges.internet_access import internet; print(internet.get_digest_for_llm('PyTorch latest stable release version site:pytorch.org'))"
} else {
  Warn "[warn] venv python not found; skip smoke checks"
}

Info "Done."
Info "Stability env (optional):"
Info "  `$env:DDGS_REGION='wt-wt' ; `$env:DDGS_TIMELIMIT='w' ; `$env:DDGS_SAFESEARCH='off'"
