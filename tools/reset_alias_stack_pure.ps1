param(
    [string]$Extra = ".\data\app\extra_routes.json"
)
$ErrorActionPreference = "Stop"

# ensure dir
$dir = Split-Path -Parent $Extra
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

# read current
$routes = @()
if (Test-Path $Extra) {
    try {
        $routes = Get-Content $Extra -Raw | ConvertFrom-Json
    } catch {
        $routes = @()
    }
}

# normalize to array of strings
$routes = @($routes) | ForEach-Object { $_.ToString() } | Where-Object { $_ -ne "" }

# remove conflicting/legacy aliases
$remove = @(
    "routes.portal_routes_alias",
    "routes.portal_routes_alias2",
    "ester.routes.portal_routes_alias",
    "ester.routes.portal_routes_alias2",
    "routes.favicon_routes_alias",
    "routes.favicon_routes_alias2",
    "ester.routes.favicon_routes_alias",
    "ester.routes.favicon_routes_alias2"
)
$routes = $routes | Where-Object { $remove -notcontains $_ }

# ensure our safe stack is present and last
$add = @(
    "routes.after_response_sanity2",
    "routes.wsgi_guard_alias",
    "routes.portal_alias_safe",
    "routes.favicon_alias_safe"
)
foreach ($m in $add) {
    if ($routes -notcontains $m) { $routes += $m }
}

# write back
$routes | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $Extra

Write-Host ("OK: wrote {0} entries to {1}" -f $routes.Count, (Resolve-Path $Extra))
