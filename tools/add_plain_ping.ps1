Param()
$path = "data\app\extra_routes.json"
$mod = "routes.plain_ping"
New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
$arr = @()
if (Test-Path $path) { try { $arr = Get-Content $path -Raw | ConvertFrom-Json } catch { $arr = @() } }
if (-not ($arr -is [System.Collections.IList])) { $arr = @() }
if ($arr -notcontains $mod) { $arr += $mod }
$arr | ConvertTo-Json -Depth 3 | Set-Content -Path $path -Encoding UTF8
"OK: added $mod"
