param(
  [switch]$InstallDDGS
)

$ErrorActionPreference = "Stop"

# ==============================
# Ester patch: web bridge diagnostics + analyst sync (PS5-safe)
# Explicit bridge: c=a+b -> accuracy requirement (a) + honest status of sensor/sources (c) => answer without hallucinations (c)
# Hidden bridges:
#   - Ashby: variety of channels (Google/serpapa/ddgs/ddg_api) + diagnostics = necessary “cook”
#   - Carpet&Thomas: channel bandwidth = 0 if the library is not installed; not to be confused with "no data"
#   - Gry's Anatomy: a patch is like a seam - adding aliases/methods without breaking the existing fabric of the system
# Erth (engineering/anatomy):
#   It’s like distinguishing between “no pulse” and “pulse not measured” - otherwise the doctor (LLM) makes a diagnosis based on silence and begins to fantasize.
# ==============================

function WriteUtf8NoBom([string]$Path, [string]$Content) {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function BackupFile([string]$Path) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $bak = "$Path.bak_$ts"
  Copy-Item -LiteralPath $Path -Destination $bak -Force
  return $bak
}

function EnsureContains([string]$Text, [string]$Needle, [string]$ErrMsg) {
  if ($Text -notmatch [regex]::Escape($Needle)) { throw $ErrMsg }
}

$proj = (Get-Location).Path
$ia   = Join-Path $proj "bridges\internet_access.py"
$an   = Join-Path $proj "modules\analyst.py"

if (!(Test-Path $ia)) { throw "Ne nayden fayl: $ia" }
if (!(Test-Path $an)) { throw "Ne nayden fayl: $an" }

if ($InstallDDGS) {
  $py = Join-Path $proj ".venv\Scripts\python.exe"
  if (!(Test-Path $py)) { throw "Ne nayden python venv: $py" }
  Write-Host "[*] Installing duckduckgo-search into venv..." -ForegroundColor Cyan
  & $py -m pip install -U duckduckgo-search
}

# --------------------------
# Patch modules/analyst.py
# --------------------------
$anText = [System.IO.File]::ReadAllText($an, [System.Text.Encoding]::UTF8)

if ($anText -notmatch "analyst_unit\s*=") {
  # 1) add process_incoming_data alias-method (if missing)
  if ($anText -notmatch "def\s+process_incoming_data\s*\(") {
    $pattern = "(\r?\n\s+def\s+_worker_loop\s*\(self\)\s*:)"
    if ($anText -notmatch $pattern) {
      throw "Ne nashel tochku vstavki v analyst.py (def _worker_loop). Fayl silno otlichaetsya ot dampa?"
    }

    $insert = @"
`n    def process_incoming_data(self, content: str, source: str, meta: dict = None):
        """"Alias for bridges.internet_access hook. Backward compatible.""""
        return self.submit_event(content, source, meta)
$1
"@

    $anText = [regex]::Replace($anText, $pattern, $insert, [System.Text.RegularExpressions.RegexOptions]::Singleline)
  }

  # 2) add analyst_unit alias after global analyst instance
  $pattern2 = "(?m)^\s*analyst\s*=\s*EsterAnalyst\(\)\s*$"
  if ($anText -notmatch $pattern2) {
    throw "Ne nashel stroku 'analyst = EsterAnalyst()' v analyst.py"
  }
  $anText = [regex]::Replace($anText, $pattern2, "analyst = EsterAnalyst()`nanalyst_unit = analyst")
  WriteUtf8NoBom -Path $an -Content $anText
  Write-Host "[OK] Patched modules/analyst.py (added process_incoming_data + analyst_unit alias)" -ForegroundColor Green
} else {
  Write-Host "[SKIP] modules/analyst.py already has analyst_unit" -ForegroundColor Yellow
}

# -------------------------------
# Patch bridges/internet_access.py
# -------------------------------
$iaText = [System.IO.File]::ReadAllText($ia, [System.Text.Encoding]::UTF8)

if ($iaText -match "PATCH:\s*web diagnostics") {
  Write-Host "[SKIP] bridges/internet_access.py already patched (web diagnostics marker found)" -ForegroundColor Yellow
} else {
  $bakIa = BackupFile $ia
  Write-Host "[*] Backup created: $bakIa" -ForegroundColor DarkGray

  # A) add diagnostics fields in __init__
  $needleKeys = "self.serpapi_engine"
  EnsureContains $iaText $needleKeys "Ne nashel self.serpapi_engine v internet_access.py"

  $patternInit = "(?m)^(\s*self\.serpapi_engine\s*=.*)$"
  $replaceInit = @"
`$1

        # PATCH: web diagnostics (fail-closed)
        self.last_provider = ""
        self.last_error = ""
        self.last_attempts = []
"@
  $iaText = [regex]::Replace($iaText, $patternInit, $replaceInit)

  # B) reset diagnostics at start of search()
  $patternSearch = "(\r?\n\s*def\s+search\s*\(self,\s*query:.*?\)\s*->\s*List\[WebResult\]\s*:\s*\r?\n\s*p\s*=\s*\(self\.provider.*?\)\.strip\(\)\.lower\(\)\s*)"
  if ($iaText -notmatch $patternSearch) {
    throw "Ne nashel signaturu def search(...) + stroku p=(self.provider...) v internet_access.py"
  }
  $iaText = [regex]::Replace(
    $iaText,
    $patternSearch,
@"
`$1

        # PATCH: reset diagnostics per call
        self.last_provider = ""
        self.last_error = ""
        self.last_attempts = []
"@,
    [System.Text.RegularExpressions.RegexOptions]::Singleline
  )

  # C) mark provider on success (google/serpapi/ddgs) — minimalno-invazivno
  $iaText = $iaText -replace "if rs:\s*return _uniq\(rs\)", "if rs:`n                try: self.last_provider = p`n                except Exception: pass`n                return _uniq(rs)"

  # D) ddgs missing lib => set last_error (do NOT look like 'no results')
  $patternDdgs = "logger\.error\(f?\"\\[DDGS\\]\s*Missing library: \{e\}\"\)\s*\r?\n\s*return \[\]"
  if ($iaText -notmatch $patternDdgs) {
    # not fatal: just a warning
    Write-Host "[WARN] Ne nashel tochnyy blok DDGS Missing library — vozmozhno fayl otlichaetsya. Perekhodim dalshe." -ForegroundColor Yellow
  } else {
    $iaText = [regex]::Replace($iaText, $patternDdgs,
@"
logger.error(f"[DDGS] Missing library: {e}")
            try:
                msg = f"DDGS missing: {e}. Install: pip install duckduckgo-search"
                self.last_error = msg
                self.last_attempts = getattr(self, 'last_attempts', [])
                self.last_attempts.append(msg)
            except Exception:
                pass
            return []
"@,
      [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
  }

  # E) fallback ddg_api: set last_provider when it returns something
  $patternFallback = "return _uniq\(self\._search_ddg_api\(q,\s*max_results\)\)"
  if ($iaText -match $patternFallback) {
    $iaText = [regex]::Replace($iaText, $patternFallback,
@"
rs = self._search_ddg_api(q, max_results)
        if rs:
            try: self.last_provider = "ddg_api"
            except Exception: pass
        return _uniq(rs)
"@)
  }

  # F) get_digest_for_llm: fail-closed with reason, timestamp, provider
  $patternDigest = "results\s*=\s*self\.search\(query,\s*max_results\)\s*\r?\n\s*if\s+not\s+results:\s*\r?\n\s*return\s+\"No relevant information found in the global network\.\""
  if ($iaText -notmatch $patternDigest) {
    throw "Ne nashel blok if not results: return 'No relevant information...' v get_digest_for_llm"
  }

  $iaText = [regex]::Replace($iaText, $patternDigest,
@"
results = self.search(query, max_results)
        if not results:
            # PATCH: fail-closed (distinguish 'disabled/broken' from 'empty')
            try:
                import datetime as _dt
                ts = _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
            except Exception:
                ts = "unknown"

            if not self.enabled():
                return f"[SEARCH_ERROR] web disabled (CLOSED_BOX=1 or WEB_FACTCHECK=never) @ {ts}"

            le = (getattr(self, "last_error", "") or "").strip()
            lp = (getattr(self, "last_provider", "") or "").strip()
            if le:
                return f"[SEARCH_ERROR] {le} @ {ts}"
            if lp:
                return f"[SEARCH_EMPTY] provider={lp}; no results for: {query} @ {ts}"
            return f"[SEARCH_EMPTY] no results for: {query} @ {ts}"
"@,
    [System.Text.RegularExpressions.RegexOptions]::Singleline
  )

  # add a marker to avoid double patch
  $iaText = $iaText + "`n`n# PATCH: web diagnostics (marker)`n"

  WriteUtf8NoBom -Path $ia -Content $iaText
  Write-Host "[OK] Patched bridges/internet_access.py (diagnostics + fail-closed)" -ForegroundColor Green
}

# --------------------------
# Smoke tests
# --------------------------
$py2 = Join-Path $proj ".venv\Scripts\python.exe"
if (Test-Path $py2) {
  Write-Host "[*] Smoke: import bridge + analyst aliases" -ForegroundColor Cyan
  & $py2 -c "from bridges.internet_access import internet; from modules.analyst import analyst_unit; print('internet:', type(internet).__name__, 'analyst_unit:', type(analyst_unit).__name__)"
} else {
  Write-Host "[WARN] venv python not found, skip smoke tests." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Next checks:" -ForegroundColor Cyan
Write-Host "  1) .\.venv\Scripts\python.exe -c `"from bridges.internet_access import internet; print(internet.get_digest_for_llm('latest stable PyTorch version'))`""
Write-Host "  2) If you see [SEARCH_ERROR] DDGS missing -> run: .\.venv\Scripts\python.exe -m pip install -U duckduckgo-search"
Write-Host "  3) Optional (fetch): set WEB_ALLOW_FETCH=1 and then use internet.read_text(url) in tool-loop (next patch if needed)."
