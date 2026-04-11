# tools\fix_synapse_section.ps1
# Hard-repair the "SISTER NODE SYNAPSE" section to restore valid syntax + optional bypass for /sister/inbound.
# A/B safety: backup + py_compile + auto-rollback.

param(
  [string]$ProjectDir = "<repo-root>",
  [string]$PyFile = "run_ester_fixed.py"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Err ($m){ Write-Host "[ERR ] $m" -ForegroundColor Red }

$path = Join-Path $ProjectDir $PyFile
if (-not (Test-Path $path)) { throw "File not found: $path" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$path.bak_synapse_$stamp"
Copy-Item -LiteralPath $path -Destination $bak -Force
Info "Backup: $bak"

# Read as UTF-8 (tolerant)
$lines = Get-Content -LiteralPath $path -Encoding UTF8

function Find-Index([string[]]$arr, [string]$pattern, [int]$start = 0){
  for ($i=$start; $i -lt $arr.Count; $i++){
    if ($arr[$i] -match $pattern) { return $i }
  }
  return -1
}

# Anchors
$idxStart = Find-Index $lines '^\s*flask_app\s*=\s*Flask\(__name__\)\s*$' 0
if ($idxStart -lt 0) { throw "Anchor not found: flask_app = Flask(__name__)" }

$idxEnd = Find-Index $lines '^\s*SISTER_NODE_URL\s*=\s*os\.getenv\("SISTER_NODE_URL"' ($idxStart + 1)
if ($idxEnd -lt 0) { throw "Anchor not found: SISTER_NODE_URL = os.getenv(...)" }
if ($idxEnd -le $idxStart) { throw "Bad anchors: end <= start" }

Info ("Replacing lines {0}..{1} (1-based)" -f ($idxStart+1), ($idxEnd))

# Canonical replacement block (keep ASCII only; no encoding surprises)
$block = @'
flask_app = Flask(__name__)

# --- register_all (safe) ---
try:
    from modules.register_all import register_all as _register_all
    _register_all(flask_app)
except Exception as e:
    logging.warning(f"[register_all] not active: {e}")

# --- autoload (safe) ---
try:
    from modules.autoload_everything import autoload_modules

    mode = os.getenv("ESTER_AUTOLOAD_MODE", "allowlist").strip().lower()
    report = autoload_modules(
        app=flask_app,
        mode=mode,
        allowlist_path="modules/autoload_allowlist.txt",
        max_failures=int(os.getenv("ESTER_AUTOLOAD_MAX_FAIL", "50")),
        log_each=bool(int(os.getenv("ESTER_AUTOLOAD_LOG_EACH", "1"))),
    )
    logging.getLogger("run_ester_fixed").info(f"[autoload] report={report}")
except Exception as e:
    logging.warning(f"[autoload] not active: {e}")

# ------------------------------------------------------------------------------
# Sister inbound bypass for request-guards (RBAC/before_request)
# Enable by setting: ESTER_SISTER_BYPASS_GUARDS=1
#
# EXPLICIT BRIDGE: c=a+b -> inbound(a) + token/limits(b) => safe exchange(c)
# HIDDEN BRIDGES: Ashby(variety via sister), Cover&Thomas(channel limit)
# GROUND: like a fuse in a power line — we let /sister/inbound pass, but token still protects payload.
# ------------------------------------------------------------------------------
def _bypass_before_request_for_paths(_app, _paths):
    import functools
    from flask import request

    norm = set()
    for p in (_paths or []):
        s = (p or "").strip()
        if not s:
            continue
        if not s.startswith("/"):
            s = "/" + s
        if len(s) > 1 and s.endswith("/"):
            s = s[:-1]
        norm.add(s)

    def _wrap(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                path = (request.path or "").strip()
                if len(path) > 1 and path.endswith("/"):
                    path = path[:-1]
                if path in norm:
                    return None
            except Exception:
                pass
            return fn(*args, **kwargs)
        return wrapped

    try:
        br = getattr(_app, "before_request_funcs", None)
        if not br:
            return False
        for bp, funcs in list(br.items()):
            if not funcs:
                continue
            br[bp] = [_wrap(f) for f in funcs]
        return True
    except Exception:
        return False

if str(os.getenv("ESTER_SISTER_BYPASS_GUARDS", "0")).strip().lower() in ("1", "true", "yes", "on"):
    ok = _bypass_before_request_for_paths(flask_app, {"/sister/inbound", "/sister/inbound/"})
    if ok:
        logging.warning("[SISTER] bypass guards enabled for /sister/inbound")
    else:
        logging.error("[SISTER] bypass guards failed")
'@

# Assemble new file
$head = @()
if ($idxStart -gt 0) { $head = $lines[0..($idxStart-1)] }

$tail = $lines[$idxEnd..($lines.Count-1)]

$newText = ($head -join "`n") + "`n" + $block + "`n" + ($tail -join "`n")

# Write UTF-8 without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($path, $newText, $utf8NoBom)
Info "Saved: $path"

# Compile (respect exit code)
$py = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Info "Compiling: $py -m py_compile $PyFile"
& $py -m py_compile $path
if ($LASTEXITCODE -ne 0){
  Err "py_compile FAILED (exit=$LASTEXITCODE). Rolling back."
  Copy-Item -LiteralPath $bak -Destination $path -Force
  throw "Compile failed; restored backup: $bak"
}

Info "OK: py_compile succeeded."