# tools\patch_load_dotenv_synapse.ps1
# Inserts python-dotenv load_dotenv() right after `flask_app = Flask(__name__)`
# Safety: backup + py_compile + rollback on failure.

param(
  [string]$ProjectDir = "D:\ester-project",
  [string]$PyFile = "run_ester_fixed.py"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Info($m){ Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Err ($m){ Write-Host "[ERR ] $m" -ForegroundColor Red }

$path = Join-Path $ProjectDir $PyFile
if (-not (Test-Path $path)) { throw "File not found: $path" }

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$path.bak_dotenv_$stamp"
Copy-Item -LiteralPath $path -Destination $bak -Force
Info "Backup: $bak"

$lines = Get-Content -LiteralPath $path -Encoding UTF8

# find flask_app = Flask(__name__)
$idx = -1
for ($i=0; $i -lt $lines.Count; $i++){
  if ($lines[$i] -match '^\s*flask_app\s*=\s*Flask\(__name__\)\s*$'){
    $idx = $i
    break
  }
}
if ($idx -lt 0) { throw "Anchor not found: flask_app = Flask(__name__)" }

# check if dotenv already inserted soon after
$already = $false
for ($j=$idx+1; $j -lt [Math]::Min($lines.Count, $idx+15); $j++){
  if ($lines[$j] -match 'from\s+dotenv\s+import\s+load_dotenv'){ $already = $true; break }
}
if ($already){
  Info "load_dotenv already present near flask_app. Nothing to do."
} else {
  $insert = @(
    "",
    "# --- .env (safe) ---",
    "try:",
    "    from dotenv import load_dotenv",
    "    load_dotenv()",
    "except Exception as e:",
    "    logging.warning(f`"[env] .env not loaded: {e}`")",
    ""
  )

  $before = $lines[0..$idx]
  $after  = $lines[($idx+1)..($lines.Count-1)]
  $lines  = @($before + $insert + $after)
  Info "Inserted load_dotenv() after flask_app = Flask(__name__)."
}

# write UTF-8 no BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($path, $lines, $utf8NoBom)
Info "Saved: $path"

# compile + rollback on failure
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