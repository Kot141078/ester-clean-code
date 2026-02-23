param(
  [string]$ProjectRoot = (Get-Location).Path
)

$Py  = Join-Path $ProjectRoot "run_ester_fixed.py"
$Vpy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $Vpy)) { $Vpy = "python" }

if (!(Test-Path $Py)) { throw "run_ester_fixed.py not found at: $Py" }

$ts  = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$Py.bak_dotenv_override_$ts"
Copy-Item $Py $bak -Force
Write-Host "[INFO] Backup: $bak"

# Read as UTF-8 (raw)
$txt = Get-Content -LiteralPath $Py -Raw -Encoding UTF8

# --- Patch 1: force load_dotenv override + explicit path (safe) ---
# Replace a plain 'load_dotenv()' line if present.
$re1 = [regex]'(?m)^\s*load_dotenv\(\)\s*$'
if ($re1.IsMatch($txt)) {
  $replacement = @"
try:
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)
except Exception:
    load_dotenv(override=True)
"@
  $txt = $re1.Replace($txt, $replacement, 1)
  Write-Host "[INFO] Patched load_dotenv(): override=True + explicit .env path"
} else {
  Write-Host "[WARN] No plain load_dotenv() line found. Skipped patch 1 (maybe already patched)."
}

# --- Patch 2: log sha256 prefix of server token (without leaking token) ---
$marker = "[SISTER] token_sha256_prefix="
if ($txt -notmatch [regex]::Escape($marker)) {
  $re2 = [regex]'(?m)^(?P<indent>\s*)SISTER_SYNC_TOKEN\s*=\s*os\.getenv\("SISTER_SYNC_TOKEN",\s*"default_token"\)\s*$'
  if ($re2.IsMatch($txt)) {
    $block = @"
`$0
${indent}try:
${indent}    import hashlib as _hashlib
${indent}    _pref = _hashlib.sha256((SISTER_SYNC_TOKEN or "").encode("utf-8","ignore")).hexdigest()[:16]
${indent}    logging.info(f"[SISTER] token_sha256_prefix={_pref}")
${indent}except Exception:
${indent}    pass
"@
    $txt = $re2.Replace($txt, $block, 1)
    Write-Host "[INFO] Inserted startup token sha256 prefix log"
  } else {
    Write-Host "[WARN] Could not find SISTER_SYNC_TOKEN assignment line. Skipped patch 2."
  }
} else {
  Write-Host "[INFO] Token sha256 prefix log already present; skipping patch 2."
}

# Write UTF-8 without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Py, $txt, $utf8NoBom)
Write-Host "[INFO] Saved: $Py"

Write-Host "[INFO] Compiling: $Vpy -m py_compile run_ester_fixed.py"
& $Vpy -m py_compile $Py
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERR ] py_compile failed; rolling back"
  Copy-Item $bak $Py -Force
  throw "Compile failed; restored backup: $bak"
}

Write-Host "[INFO] OK: patch applied and py_compile succeeded"