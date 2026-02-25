# patch_sister_token_debug.ps1
# Purpose: make Sister token debugging safe (sha256 prefix only) + strict .env loading + robust expected-token lookup.
# A/B safety: patch -> py_compile -> rollback on failure.
#
# Explicit BRIDGE: c=a+b - incoming stimulus (a) + procedural check of token/source (c) => admission to exchange (c).
# SKRYTYE MOSTY:
#   - Ashby: boil - a token as the minimum “distinguishability” of nodes in the channel.
#   - Carpet&Thomas: capacity channel - we log only the hash prefix (we compress it, we don’t drag the secret).
# EARTHLY Paragraph: like a gasket in a hydraulic system - it holds pressure and does not allow the connection to “snot”, but by itself it does not pump anything.

$ErrorActionPreference = "Stop"

$proj = Split-Path -Parent $PSScriptRoot
$path = Join-Path $proj "run_ester_fixed.py"
$py   = Join-Path $proj ".venv\Scripts\python.exe"

if (!(Test-Path $path)) { throw "run_ester_fixed.py not found: $path" }
if (!(Test-Path $py))   { throw "python venv not found: $py" }

$ts  = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$path.bak_sistertok_$ts"
Copy-Item $path $bak -Force
Write-Host "[INFO] Backup: $bak"

# read as UTF-8 (raw)
$src = Get-Content -LiteralPath $path -Raw -Encoding UTF8

# --- 1) Strict load_dotenv: use .env next to this file, override=True ---
if ($src -notmatch "\[env\]\s+\.env loaded=") {
  # replace a lone 'load_dotenv()' line (first match)
  $pattern = "(?m)^\s*load_dotenv\(\)\s*$"
  $replacement = @"
try:
    _dotenv_path = str(Path(__file__).resolve().parent / ".env")
    _loaded = load_dotenv(dotenv_path=_dotenv_path, override=True)
    logging.info(f"[env] .env loaded={_loaded} path={_dotenv_path}")
except Exception as _e:
    try:
        logging.warning(f"[env] load_dotenv failed: {_e}")
    except Exception:
        pass
"@

  if ([System.Text.RegularExpressions.Regex]::IsMatch($src, $pattern)) {
    $src = [System.Text.RegularExpressions.Regex]::Replace($src, $pattern, $replacement, 1)
    Write-Host "[INFO] Patched strict load_dotenv()"
  } else {
    Write-Host "[WARN] No plain load_dotenv() line found; skipped dotenv patch."
  }
} else {
  Write-Host "[INFO] dotenv patch already present."
}

# --- 2) Startup log: expected token sha256 prefix (no token leak) ---
if ($src -notmatch "token_sha256_prefix") {
  $patTok = '(?m)^(SISTER_SYNC_TOKEN\s*=\s*os\.getenv\("SISTER_SYNC_TOKEN",\s*"default_token"\)\.strip\(\)\s*)$'
  $insTok = @"
`$1
try:
    import hashlib
    _h = hashlib.sha256((SISTER_SYNC_TOKEN or "").encode("utf-8", "ignore")).hexdigest()[:16]
    logging.info(f"[SISTER] token_sha256_prefix={_h} len={len(SISTER_SYNC_TOKEN)}")
except Exception:
    pass
"@
  if ([System.Text.RegularExpressions.Regex]::IsMatch($src, $patTok)) {
    $src = [System.Text.RegularExpressions.Regex]::Replace($src, $patTok, $insTok, 1)
    Write-Host "[INFO] Inserted startup token sha256 prefix log."
  } else {
    Write-Host "[WARN] Could not find SISTER_SYNC_TOKEN assignment line; skipped startup log insert."
  }
} else {
  Write-Host "[INFO] Startup token prefix log already present."
}

# --- 3) Inbound check: compare token vs expected (env overrides) + log sha16 prefixes on mismatch ---
if ($src -notmatch "\[SISTER\]\s+Invalid token recv=") {
  $patInbound = @"
(?ms)
token\s*=\s*\(data\.get\("token"\)\s*or\s*""\)\.strip\(\)\s*
if\s+not\s+SISTER_SYNC_TOKEN\s+or\s+token\s*!=\s*SISTER_SYNC_TOKEN\s*:\s*
\s*return\s+jsonify\(\{\s*"status"\s*:\s*"error"\s*,\s*"message"\s*:\s*"Invalid token"\s*\}\)\s*,\s*403
"@

  $repInbound = @"
token = (data.get("token") or "").strip()
expected = (os.getenv("SISTER_SYNC_TOKEN") or SISTER_SYNC_TOKEN or "").strip()

if not expected:
    logging.warning("[SISTER] inbound token not set (expected empty).")
    return jsonify({"status": "error", "message": "Server token not set"}), 500

if token != expected:
    try:
        import hashlib
        def _sha16(x: str) -> str:
            return hashlib.sha256((x or "").encode("utf-8", "ignore")).hexdigest()[:16]
        logging.warning(
            f"[SISTER] Invalid token recv={_sha16(token)} exp={_sha16(expected)} "
            f"recv_len={len(token)} exp_len={len(expected)}"
        )
    except Exception:
        pass
    return jsonify({"status": "error", "message": "Invalid token"}), 403
"@

  if ([System.Text.RegularExpressions.Regex]::IsMatch($src, $patInbound)) {
    $src = [System.Text.RegularExpressions.Regex]::Replace($src, $patInbound, $repInbound, 1)
    Write-Host "[INFO] Patched /sister/inbound token check with sha16 debug."
  } else {
    Write-Host "[WARN] Could not match inbound token check block; skipped."
  }
} else {
  Write-Host "[INFO] Inbound sha16 debug already present."
}

# save
Set-Content -LiteralPath $path -Value $src -Encoding UTF8
Write-Host "[INFO] Saved: $path"

# compile + rollback
Write-Host "[INFO] Compiling: $py -m py_compile run_ester_fixed.py"
& $py -m py_compile $path
if ($LASTEXITCODE -ne 0) {
  Write-Host "[ERR ] py_compile failed. Rolling back."
  Copy-Item $bak $path -Force
  throw "Compile failed; restored backup: $bak"
}
Write-Host "[INFO] OK: py_compile succeeded."