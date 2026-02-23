Param([string]$ShareName = "ester-data")
$share = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
if ($share) {
  Remove-SmbShare -Name $ShareName -Force
  "{""ok"":true,""removed"":""$ShareName""}"
} else {
  "{""ok"":true,""removed"":false}"
}
