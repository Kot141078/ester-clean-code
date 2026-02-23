Param(
  [string[]]$Modules = @(
    "routes.favicon_routes_alias",
    "routes.portal_routes_alias",
    "routes.jwt_owner_routes",
    "app_plugins.autoregister_compat_pydantic",
    "routes.portal_routes_alias2",
    "routes.favicon_routes_alias2"
  )
)
$path = "data\app\extra_routes.json"
New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
$existing = @()
if (Test-Path $path) {
  try { $existing = Get-Content $path -Raw | ConvertFrom-Json } catch { $existing = @() }
}
if (-not ($existing -is [System.Collections.IList])) { $existing = @() }
$set = New-Object System.Collections.Generic.HashSet[string]
foreach ($m in $existing) { [void]$set.Add([string]$m) }
foreach ($m in $Modules) { [void]$set.Add([string]$m) }
$final = @()
foreach ($m in $set) { $final += $m }
$final | ConvertTo-Json -Depth 3 | Set-Content -Path $path -Encoding UTF8
"OK: wrote $path with $($final.Count) entries"
