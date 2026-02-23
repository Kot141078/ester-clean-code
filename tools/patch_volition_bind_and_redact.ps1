# tools/patch_volition_bind_and_redact.ps1
# - Adds missing VolitionSystem.social_synapse_cycle binder (noop-safe)
# - Redacts Telegram bot token from logs and silences httpx/httpcore INFO
# - Backup + py_compile + auto-rollback on failure

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "[OK]  $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Write-Err($m)  { Write-Host "[ERR] $m" -ForegroundColor Red }

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$target = Join-Path $repo "run_ester_fixed.py"

if (-not (Test-Path $target)) {
  throw "Target not found: $target"
}

Write-Info "Repo root : $repo"
Write-Info "Target    : $target"

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = "$target.bak_$ts"

Copy-Item $target $backup -Force
Write-Ok "Backup: $backup"

# Read (fast)
$txt = [System.IO.File]::ReadAllText($target, [System.Text.Encoding]::UTF8)

$marker = "# --- PATCH: social_synapse_bind_v1 ---"
if ($txt.Contains($marker)) {
  Write-Ok "Patch already present. Nothing to do."
  exit 0
}

$snippet = @"
$marker
def _ester_bind_social_synapse_v1():
    # Bind VolitionSystem.social_synapse_cycle if missing.
    # If a standalone social_synapse_cycle() exists, delegate to it.
    try:
        VS = globals().get("VolitionSystem")
        if VS and not hasattr(VS, "social_synapse_cycle"):
            def _vs_social_synapse_cycle(self, *args, **kwargs):
                fn = globals().get("social_synapse_cycle")
                if callable(fn) and fn is not _vs_social_synapse_cycle:
                    try:
                        return fn(self, *args, **kwargs)
                    except TypeError:
                        return fn(*args, **kwargs)
                return None
            VS.social_synapse_cycle = _vs_social_synapse_cycle
    except Exception:
        pass

_ester_bind_social_synapse_v1()

# --- PATCH: redact_telegram_httpx_logs_v1 ---
def _ester_redact_telegram_httpx_logs_v1():
    # Prevent bot token leakage in logs like:
    # "https://api.telegram.org/bot<token>/getUpdates"
    try:
        import re as _re
        import logging as _logging

        _pat = _re.compile(r"(https://api\.telegram\.org/)(bot)(\d+:[A-Za-z0-9_-]+)")

        class _RedactFilter(_logging.Filter):
            def filter(self, record):
                try:
                    msg = record.getMessage()
                    if msg and "api.telegram.org/bot" in msg:
                        record.msg = _pat.sub(r"\1bot<redacted>", msg)
                        record.args = ()
                except Exception:
                    pass
                return True

        flt = _RedactFilter()

        root = _logging.getLogger()
        root.addFilter(flt)

        for name in ("httpx", "httpcore", "telegram", "telegram.ext"):
            try:
                lg = _logging.getLogger(name)
                lg.addFilter(flt)
            except Exception:
                pass

        # Also stop noisy INFO that prints URLs
        try:
            _logging.getLogger("httpx").setLevel(_logging.WARNING)
            _logging.getLogger("httpcore").setLevel(_logging.WARNING)
        except Exception:
            pass

    except Exception:
        pass

_ester_redact_telegram_httpx_logs_v1()
"@

# Insert BEFORE if __name__ == "__main__": (important: code must run before main loop)
$re = [regex]"(?m)^(if\s+__name__\s*==\s*['""]__main__['""]\s*:)"
$m = $re.Match($txt)

if ($m.Success) {
  $idx = $m.Index
  $newTxt = $txt.Substring(0, $idx) + $snippet + "`r`n`r`n" + $txt.Substring($idx)
  Write-Info "Inserted patch before __main__ guard."
} else {
  $newTxt = $txt + "`r`n`r`n" + $snippet + "`r`n"
  Write-Warn "No __main__ guard found; appended patch at end."
}

# Write UTF-8 without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($target, $newTxt, $utf8NoBom)
Write-Ok "Written: $target"

Write-Info "py_compile..."
try {
  python -m py_compile $target | Out-Null
  Write-Ok "py_compile OK"
} catch {
  Write-Err "py_compile FAILED. Rolling back..."
  Copy-Item $backup $target -Force
  throw
}

Write-Ok "Done."
exit 0