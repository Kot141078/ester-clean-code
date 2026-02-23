
Param()
$ErrorActionPreference = "Stop"
$extra = "data\app\extra_routes.json"
$dir = Split-Path $extra -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }

$arr = @()
if (Test-Path $extra) {
    try {
        $raw = Get-Content -LiteralPath $extra -Raw -ErrorAction Stop
        if ($raw.Trim().Length -gt 0) {
            $arr = $raw | ConvertFrom-Json
        }
    } catch {
        $arr = @()
    }
}
if ($arr -eq $null) { $arr = @() }
$tmp = @()
foreach ($x in $arr) { $tmp += [string]$x }
$arr = $tmp

$need = @(
  "routes.favicon_routes_alias2",
  "routes.portal_routes_alias2",
  "app_plugins.after_response_sanity"
)
foreach ($m in $need) {
    if (-not ($arr -contains $m)) { $arr += $m }
}
$arr = $arr | Where-Object { $_ -ne "app_plugins.after_response_sanity" }
$arr += "app_plugins.after_response_sanity"

$json = $arr | ConvertTo-Json -Compress -Depth 4
$json | Out-File -Encoding UTF8 -LiteralPath $extra
Write-Host ("OK: ensured after_response_sanity is last ({0} entries)" -f $arr.Count)
