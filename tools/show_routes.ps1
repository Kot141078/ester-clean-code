$path = "data\app\extra_routes.json"
if (Test-Path $path) {
  Get-Content $path -Raw | Write-Output
} else {
  "extra_routes.json not found at $path" | Write-Output
}
