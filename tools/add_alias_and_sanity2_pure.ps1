Param(
  [string]$File = "data/app/extra_routes.json"
)
New-Item -ItemType Directory -Force -Path (Split-Path $File) | Out-Null
$want = @(
  "routes.favicon_routes_alias2",
  "routes.portal_routes_alias2",
  "app_plugins.after_response_sanity2"
)
if (Test-Path $File) {
  $cur = Get-Content -Raw -Path $File | ConvertFrom-Json
} else {
  $cur = @()
}
# merge unique
$set = New-Object System.Collections.Generic.HashSet[string]
$merged = @()
foreach ($m in $cur) { if ($set.Add($m)) { $merged += $m } }
foreach ($m in $want) { if ($set.Add($m)) { $merged += $m } }
# save
$merged | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 -Path $File
Write-Host ("OK: wrote {0} entries to {1}" -f $merged.Count, $File)
