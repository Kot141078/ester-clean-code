Param(
  [Parameter(Mandatory=$true)][string]$ManifestPath,
  [string]$TasksPath="configs\evojudge_tasks.json",
  [string]$Adapter="dummy",
  [string]$Label="family"
)
# PS5 friendly, no special modules.
$manifest = Get-Content -Raw -Encoding UTF8 $ManifestPath | ConvertFrom-Json
foreach($node in $manifest.nodes){
  $root = $node.data_root
  Write-Host "== EvoJudge on" $node.id "->" $root
  $env:ESTER_DATA_ROOT = $root
  $env:AB_MODE = "A"
  python tools\evojudge_run.py --adapter $Adapter --tasks $TasksPath --label "$Label-$($node.id)"
}
