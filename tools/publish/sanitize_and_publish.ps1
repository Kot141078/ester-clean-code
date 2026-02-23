Param(
  [string]$RepoUrl = "https://github.com/Kot141078/Ester-Code.git",
  [string]$Branch = "main",
  [string]$ExportDir = ".export\ester_code_publish",
  [switch]$ForcePush = $true
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[publish] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "[publish] $msg" -ForegroundColor Green }

$src = (Resolve-Path ".").Path
$dst = Join-Path $src $ExportDir

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
  ".ester_env_state.json", "Ester_dump_part_*.txt", "Log.txt", "tools\Log.txt",
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

