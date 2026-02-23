Param(
  [string[]]$Files = @(".\cautious_bootstrap_routes.py", ".\cron_routes.py", ".\self_forge_guarded_routes.py")
)
$ErrorActionPreference = "Stop"
foreach($f in $Files){
  if(Test-Path $f){
    $txt = Get-Content $f -Raw -Encoding UTF8
    if($txt -notmatch "(?m)^\s*import\s+os\b"){
      "import os`n" + $txt | Set-Content $f -Encoding UTF8
      Write-Host "[patched]" $f
    } else {
      Write-Host "[ok]" $f "already has import os"
    }
  } else {
    Write-Host "[skip]" $f "not found"
  }
}
