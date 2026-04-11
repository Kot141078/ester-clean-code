Param(
  [string]$RepoUrl = "https://github.com/Kot141078/ester-clean-code.git",
  [string]$Branch = "main",
  [string]$ExportDir = ".export\ester_code_publish",
  [switch]$ForcePush
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[publish] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[publish] $msg" -ForegroundColor Green }

function Resolve-Python {
  $candidate = Get-Command python -ErrorAction SilentlyContinue
  if ($candidate) { return $candidate.Source }
  $candidate = Get-Command py -ErrorAction SilentlyContinue
  if ($candidate) { return "$($candidate.Source) -3" }
  throw "Python launcher not found in PATH."
}

$src = (Resolve-Path ".").Path
$dst = Join-Path $src $ExportDir

$gitStatus = git -C $src status --short
if ($LASTEXITCODE -ne 0) {
  throw "git status failed in source tree."
}
if ($gitStatus) {
  throw "Source tree is dirty. Refusing to publish sanitized snapshot from an uncommitted state."
}

$gate = Join-Path $src "tools\check_public_release_safety.py"
if (Test-Path $gate) {
  Write-Info "Running public release safety gate..."
  $pythonCmd = Resolve-Python
  if ($pythonCmd -like "* *") {
    & cmd /c "$pythonCmd `"$gate`""
  } else {
    & $pythonCmd $gate
  }
  if ($LASTEXITCODE -ne 0) {
    throw "Public release safety gate failed. Refusing publish."
  }
}

if (Test-Path $dst) {
  Write-Info "Removing previous export dir: $dst"
  Remove-Item -Recurse -Force $dst
}

Write-Info "Exporting sanitized snapshot..."
New-Item -ItemType Directory -Force -Path $dst | Out-Null

# Robocopy exclusions (privacy + large stores)
$xd = @(
  ".git", ".venv", "venv", "data", "vstore", "chroma", "logs", "state",
  "telegram_files", "patch_backups", "_patch3", "_rag_test_docs", "models--*",
  "secrets", "out_log"
)
$xf = @(
  ".env", ".env.*", "*.jsonl", "*.log", "*.sqlite", "*.sqlite3", "*.db",
  "*.key", "*.pem", "*.p12", "*.crt", "*.token", "*.secrets", "secrets.*",
  ".ester_env_state.json", "qa.json", "resp.json", "dod_status.json", "net_search_log_dump.json",
  "Ester_dump_part_*.txt", "Log.txt", "tools\Log.txt",
  "top_errors.tsv", "top_warnings.tsv", "warnings.tsv"
)

# Copy everything except exclusions
robocopy $src $dst /E /XD $xd /XF $xf /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
Write-Ok "Export complete."

Push-Location $dst
try {
  Write-Info "Initializing temporary git repo..."
  git init | Out-Null
  git checkout -b $Branch | Out-Null
  git add -A
  git -c core.hooksPath=NUL -c commit.gpgSign=false commit -m "Sanitized publish" | Out-Null
  git remote add origin $RepoUrl
  if ($ForcePush) {
    git -c core.hooksPath=NUL push -u origin HEAD:$Branch --force
  } else {
    git -c core.hooksPath=NUL push -u origin HEAD:$Branch
  }
  Write-Ok "Push complete: $RepoUrl ($Branch)"
} finally {
  Pop-Location
}

