
Param()

# PS5-sovmestimo. Ne trebuet podpisi.
$ErrorActionPreference = 'Stop'

$root = Get-Location
$dataDir = Join-Path $root 'data'
$appDir  = Join-Path $dataDir 'app'
$json    = Join-Path $appDir 'extra_routes.json'

New-Item -ItemType Directory -Force -Path $appDir | Out-Null

$modulesToAdd = @(
  'routes.portal_routes_alias2',
  'routes.favicon_alias2',
  'middleware.after_response_sanity2',
  'middleware.wsgi_guard_alias'
)

$current = @()
if (Test-Path $json) {
  try {
    $raw = Get-Content -Raw -Path $json
    if ($raw) { $current = $raw | ConvertFrom-Json }
    if ($current -eq $null) { $current = @() }
  } catch {
    $current = @()
  }
}

# Zaschita ot dublikatov
$set = New-Object System.Collections.Generic.HashSet[string]
foreach ($m in $current) { [void]$set.Add([string]$m) }

foreach ($m in $modulesToAdd) {
  if (-not $set.Contains($m)) {
    [void]$set.Add($m)
  }
}

$out = @()
foreach ($m in $set) { $out += $m }

$out | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -Path $json

Write-Output ("OK: wrote {0} entries to {1}" -f $out.Count, $json)
