Param()
$path = "data\app\extra_routes.json"
New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
$mods = @("routes.diag_routes","app_plugins.boot_log")
if (Test-Path $path) {
  try { $arr = Get-Content $path -Raw | ConvertFrom-Json } catch { $arr = @() }
} else { $arr = @() }
if (-not ($arr -is [System.Collections.IList])) { $arr = @() }
foreach ($m in $mods) { if ($arr -notcontains $m) { $arr += $m } }
$arr | ConvertTo-Json -Depth 3 | Set-Content -Path $path -Encoding UTF8
"OK: added diag modules to $path"
