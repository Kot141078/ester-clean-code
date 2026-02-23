Param(
  [string]$ProjectRoot = (Get-Location).Path
)
$path = Join-Path $ProjectRoot "data\app\extra_routes.json"
$new = @("routes.portal_routes_alias","routes.favicon_fallback_routes")

if (-not (Test-Path $path)) {
  New-Item -ItemType Directory -Force -Path (Split-Path $path) | Out-Null
  $obj = $new
} else {
  try {
    $obj = Get-Content $path -Raw | ConvertFrom-Json
  } catch {
    $obj = @()
  }
  if ($obj -isnot [System.Collections.IEnumerable]) { $obj = @() }
  foreach($m in $new){
    if (-not ($obj -contains $m)) { $obj += $m }
  }
}
$json = ($obj | ConvertTo-Json -Depth 4)
Set-Content -Path $path -Value $json -Encoding UTF8
Write-Host "[ok] updated" $path
Write-Host $json
