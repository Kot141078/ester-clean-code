#requires -Version 5.1
[CmdletBinding()]
param(
  [string]$PersistDir = ""
)

$ErrorActionPreference = "Continue"

if (-not $PersistDir) {
  if ($env:PERSIST_DIR) {
    $PersistDir = $env:PERSIST_DIR
  } else {
    $PersistDir = (Join-Path (Get-Location) "data")
  }
}

$root = (Resolve-Path -LiteralPath $PersistDir -ErrorAction SilentlyContinue)
if (-not $root) {
  Write-Host "[WARN] persist dir not found: $PersistDir"
  exit 0
}

$rootPath = $root.Path
$targets = @(
  (Join-Path $rootPath "garage\agents"),
  (Join-Path $rootPath "capability_drift")
)

$user = "$env:USERDOMAIN\$env:USERNAME"
$changed = @()

foreach ($t in $targets) {
  if (-not (Test-Path -LiteralPath $t)) {
    continue
  }
  try {
    icacls $t /inheritance:r | Out-Null
    icacls $t /remove "Users" | Out-Null
    icacls $t /grant:r "$user:(OI)(CI)M" | Out-Null
    $changed += $t
  } catch {
    Write-Host "[WARN] ACL hardening skipped for $t : $($_.Exception.Message)"
  }
}

Write-Host ("[INFO] ACL hardening targets changed: {0}" -f $changed.Count)
foreach ($c in $changed) {
  Write-Host ("  - " + $c)
}
exit 0

