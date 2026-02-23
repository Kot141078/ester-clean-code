Param(
  [string[]]$FileNames = @("cautious_bootstrap_routes.py","cron_routes.py","self_forge_guarded_routes.py"),
  [string]$Root = "."
)
$ErrorActionPreference = "Stop"
$files = Get-ChildItem -Path $Root -Recurse -File | Where-Object { $FileNames -contains $_.Name }
foreach($f in $files){
  $txt = Get-Content $f.FullName -Raw -Encoding UTF8
  if($txt -notmatch "(?m)^\s*import\s+os\b"){
    "import os`n" + $txt | Set-Content $f.FullName -Encoding UTF8
    Write-Host "[patched]" $($f.FullName)
  } else {
    Write-Host "[ok]" $($f.FullName) "already has import os"
  }
}
