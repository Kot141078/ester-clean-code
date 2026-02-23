# Adds safe portal & favicon aliases only; cleans conflicting older aliases.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\add_portal_safe_only.ps1

$ErrorActionPreference = 'Stop'

$root = $env:ESTER_DATA_ROOT
if (-not $root -or -not (Test-Path $root)) {
  $root = Join-Path (Get-Location) 'data'
}

$dir  = Join-Path $root 'app'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$file = Join-Path $dir 'extra_routes.json'

# load existing as array
if (Test-Path $file) {
  $raw = Get-Content $file -Raw
  if ($raw.Trim().Length -gt 0) {
    $items = $raw | ConvertFrom-Json
  } else { $items = @() }
} else { $items = @() }

if ($items -eq $null) { $items = @() }
if ($items -isnot [System.Collections.IEnumerable]) { $items = @($items) }

# remove conflicting aliases (both "ester.routes.*" and bare "routes.*")
$bad = @(
  'ester.routes.portal_routes_alias.register()',
  'ester.routes.portal_routes_alias2.register()',
  'ester.routes.favicon_routes_alias.register()',
  'ester.routes.favicon_alias2.register()',
  'routes.portal_routes_alias.register()',
  'routes.portal_routes_alias2.register()',
  'routes.favicon_routes_alias.register()',
  'routes.favicon_alias2.register()'
)

$want = @(
  'ester.routes.portal_alias_safe.register()',
  'ester.routes.favicon_alias_safe.register()'
)

# keep others, drop bad
$items = @($items | Where-Object { $_ -and ($_ -notin $bad) })

# de-dup and append "want" to the end
$set   = New-Object 'System.Collections.Generic.HashSet[string]'
$final = New-Object 'System.Collections.Generic.List[string]'
foreach ($i in $items) { if ($i -and $set.Add($i)) { [void]$final.Add($i) } }
foreach ($i in $want)  { if ($i -and $set.Add($i)) { [void]$final.Add($i) } }

$final | ConvertTo-Json -Depth 4 | Set-Content -Path $file -Encoding UTF8
Write-Host "OK: wrote $($final.Count) entries to $file"
