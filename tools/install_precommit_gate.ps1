#requires -Version 5.1
<#
Installs Ester pre-commit gate in a repo-safe way:
- sets core.hooksPath to .githooks (versioned hooks)
- validates presence of .githooks/pre-commit
Offline only.
#>

$ErrorActionPreference = "Stop"

function Fail($msg) {
  Write-Host "[install_precommit_gate] ERROR: $msg" -ForegroundColor Red
  exit 2
}

try {
  $repoRoot = (git rev-parse --show-toplevel) 2>$null
} catch {
  Fail "Not a git repository (git rev-parse failed). Run from inside D:\ester-project."
}

if (-not $repoRoot) { Fail "Could not detect repo root." }

$hookPath = Join-Path $repoRoot ".githooks"
$hookFile = Join-Path $hookPath "pre-commit"

if (-not (Test-Path $hookFile)) {
  Fail "Missing $hookFile. Ensure .githooks/pre-commit exists in the repo."
}

# Set hooks path (versioned)
git -C $repoRoot config core.hooksPath ".githooks" | Out-Null

# Verify
$val = (git -C $repoRoot config --get core.hooksPath)
if ($val -ne ".githooks") {
  Fail "Failed to set core.hooksPath. Got: $val"
}

Write-Host "[install_precommit_gate] OK installed core.hooksPath=.githooks" -ForegroundColor Green
Write-Host "[install_precommit_gate] Verify:" -ForegroundColor Yellow
Write-Host "  git config --get core.hooksPath"
Write-Host "[install_precommit_gate] Test (should be OK):" -ForegroundColor Yellow
Write-Host "  python -B tools/route_registry_check.py"
Write-Host "  python -B tools/route_return_lint.py"
