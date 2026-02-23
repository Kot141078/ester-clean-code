
Param(
  [string]$JsonPath = "data\app\extra_routes.json"
)
# PS5-compatible, no Python required

$modules = @(
  "routes.favicon_routes_alias2",
  "routes.portal_routes_alias2",
  "routes.lan_hub_routes"
)

$dir = Split-Path -Parent $JsonPath
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

if (Test-Path $JsonPath) {
  try {
    $current = Get-Content $JsonPath -Raw | ConvertFrom-Json
  } catch {
    $current = @()
  }
} else { $current = @() }

if ($current -isnot [System.Collections.IEnumerable]) { $current = @() }

$set = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($m in $current) { [void]$set.Add([string]$m) }
foreach ($m in $modules)  { [void]$set.Add([string]$m) }

$out = @($set) | Sort-Object
$out | ConvertTo-Json | Set-Content -Path $JsonPath -Encoding UTF8
Write-Host "OK: wrote $JsonPath with $($out.Count) entries"
