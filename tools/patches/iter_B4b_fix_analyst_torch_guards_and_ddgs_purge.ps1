<#
Ester patch B4b (PS5-safe)

Explicit bridge (c=a+b):
  (a) trebovanie "tochnost do tsifry" + (b) chestnye sensory/diagnostika i sovmestimost moduley
  => (c) sistema NE ugadyvaet pri slomannom sensore.

Hidden bridges:
  - Ashby: raznoobrazie kanalov + zhestkiy kontrol kachestva (ne verim shumu)
  - Cover&Thomas: esli kanal ne dostavil paket, nelzya "dekodirovat" tishinu kak fakt
  - Gray's Anatomy: stavim "sukhozhilie" (shim) mezhdu modulem i zavisimostyu, chtoby ne rvat tkan importami

Earth (inzheneriya/anatomiya):
  Eto kak tonometr bez manzhety: pravilnyy vyvod — "manzhety net", a ne "120/80".
#>

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [switch]$PurgeLegacyDuckDuckGoSearch
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

$proj = (Resolve-Path -LiteralPath $ProjectRoot).Path
Info "ProjectRoot: $proj"

$py = Join-Path $proj ".venv\Scripts\python.exe"
if (!(Test-Path $py)) { Die "venv python not found: $py" }

if ($PurgeLegacyDuckDuckGoSearch) {
  Info "[pip] Uninstalling legacy duckduckgo-search (to avoid fallback & warnings)..."
  try { & $py -m pip uninstall -y duckduckgo-search | Out-Host } catch { }
}

$an = Join-Path $proj "modules\analyst.py"
$ia = Join-Path $proj "bridges\internet_access.py"
if (!(Test-Path $an)) { Die "Missing file: $an" }
if (!(Test-Path $ia)) { Die "Missing file: $ia" }

$bakAn = BackupFile $an
$bakIa = BackupFile $ia
Info "Backups:"
Info "  $bakAn"
Info "  $bakIa"

try {
  # --------------------------
  # 1) Fix modules/analyst.py: guards when torch is None
  # --------------------------
  $t = ReadAll $an
  $orig = $t

  # Ensure we have guard helpers once
  if ($t -match "torch\s*=\s*None" -and $t -notmatch "PATCH:\s*torch guards") {
    Info "[patch] analyst.py: add torch guards (HAS_TORCH/HAS_CUDA/_cuda_device_count)"
    $guard = @"

# PATCH: torch guards
HAS_TORCH = torch is not None
HAS_CUDA  = HAS_TORCH and hasattr(torch, "cuda") and torch.cuda.is_available()

def _cuda_device_count():
    return torch.cuda.device_count() if HAS_CUDA else 0
"@

    # Insert guards right after the optional torch block if possible
    $t = $t -replace "(# PATCH: torch optional[\s\S]*?torch\s*=\s*None\s*)", "`$1$guard"
  }

  # Replace unsafe module-level usage patterns
  #  - torch.cuda.device_count()  -> _cuda_device_count()
  #  - torch.cuda.is_available()  -> HAS_CUDA
  $t = $t -replace "torch\.cuda\.device_count\(\)", "_cuda_device_count()"
  $t = $t -replace "torch\.cuda\.is_available\(\)", "HAS_CUDA"

  if ($t -ne $orig) {
    WriteUtf8Bom $an $t
  } else {
    Warn "[skip] analyst.py: nothing to change (guards may already exist)"
  }

  # --------------------------
  # 2) Fix bridges/internet_access.py: ddgs-only (no duckduckgo_search fallback)
  # --------------------------
  $t2 = ReadAll $ia
  $orig2 = $t2

  # Remove any direct legacy import
  $t2 = $t2 -replace "(?m)^\s*from\s+duckduckgo_search\s+import\s+DDGS\s*$", "from ddgs import DDGS  # ddgs-only"

  # Replace try/except fallback block if present
  $t2 = $t2 -replace "(?ms)try:\s*?\r?\n\s*from\s+ddgs\s+import\s+DDGS[^\r\n]*\r?\n\s*except\s+Exception:\s*?\r?\n\s*from\s+duckduckgo_search\s+import\s+DDGS[^\r\n]*",
@"
try:
    from ddgs import DDGS  # ddgs-only
except Exception as _e:
    DDGS = None
    _DDGS_IMPORT_ERROR = str(_e)
"@

  # Before any "with DDGS() as ddgs:" add a guard (first occurrence only)
  if ($t2 -match "with\s+DDGS\(\)\s+as\s+ddgs:" -and $t2 -notmatch "ddgs unavailable") {
    Info "[patch] internet_access.py: guard DDGS None -> fail-closed"
    $t2 = $t2 -replace "with\s+DDGS\(\)\s+as\s+ddgs:",
@"
if DDGS is None:
            logger.error(f"[DDGS] ddgs unavailable: {_DDGS_IMPORT_ERROR}")
            try:
                self.last_error = f"ddgs unavailable: {_DDGS_IMPORT_ERROR}"
            except Exception:
                pass
            return []
        with DDGS() as ddgs:
"@
  }

  # If digest still has the old generic message, keep the SEARCH_EMPTY marker style
  $t2 = $t2 -replace 'return\s+"No relevant information found in the global network\."', 'return f"[SEARCH_EMPTY] no results for: {query}"'

  if ($t2 -ne $orig2) {
    WriteUtf8Bom $ia $t2
  } else {
    Warn "[skip] internet_access.py: nothing to change"
  }

  Info "[OK] Patch applied."
}
catch {
  Warn "[FAIL] Patch failed. Rolling back..."
  Copy-Item -LiteralPath $bakAn -Destination $an -Force
  Copy-Item -LiteralPath $bakIa -Destination $ia -Force
  throw
}

# --------------------------
# Smoke tests
# --------------------------
Info "[smoke] analyst import should not crash without torch"
& $py -c "from modules.analyst import analyst_unit; print('analyst_unit ok:', hasattr(analyst_unit,'process_incoming_data'))"

Info "[smoke] ensure no legacy duckduckgo_search remains in internet_access.py"
& $py -c "import pathlib; p=pathlib.Path('bridges/internet_access.py').read_text(encoding='utf-8', errors='ignore'); print('duckduckgo_search' in p)"

Info "[smoke] ddgs works"
& $py -c "from ddgs import DDGS; print('ddgs ok')"

Info "[smoke] web digest"
& $py -c "from bridges.internet_access import internet; print(internet.get_digest_for_llm('PyTorch latest stable release version site:pytorch.org'))"

Info "Done."
Info "Tip (optional):"
Info "  `$env:DDGS_REGION='us-en' ; `$env:DDGS_TIMELIMIT='w' ; `$env:DDGS_SAFESEARCH='off'"
