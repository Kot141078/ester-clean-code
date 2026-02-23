param([int]$Tail=10)
$path = Join-Path $HOME ".ester\vstore\ester_chat_log.json"
if (-not (Test-Path $path)) { Write-Host "Net loga: $path"; exit 1 }
$data = Get-Content $path -Raw | ConvertFrom-Json
$data | Select-Object -Last $Tail | ForEach-Object {
  $ts = $_.ts
  $sid = $_.sid
  $mode = $_.response.mode
  $prov = $_.response.provider
  $ans = $_.response.answer
  "{0}  sid={1}  mode={2} prov={3}  {4}" -f $ts,$sid,$mode,$prov,($ans -replace "`r?`n"," " -replace "\s+"," ").Substring(0,[Math]::Min(80,($ans|Out-String).Length))
}
