Param(
  [string]$Drive = "Z",
  [string]$UNC = "",
  [switch]$Persist = $true,
  [string]$User = "",
  [string]$Password = ""
)
$Drive = $Drive.TrimEnd(':') + ":"
if (-not $UNC) {
  if ($env:ESTER_LANHUB_UNC) { $UNC = $env:ESTER_LANHUB_UNC } else { throw "UNC is required (e.g. \\Host\ester-data)" }
}
& cmd.exe /c "net use $Drive /delete /y" | Out-Null
$opts = "/persistent:{0}" -f ($(if ($Persist) {"yes"} else {"no"}))
if ($User -and $Password) {
  & cmd.exe /c "net use $Drive `"$UNC`" /user:`"$User`" `"$Password`" $opts"
} else {
  & cmd.exe /c "net use $Drive `"$UNC`" $opts"
}
if ($LASTEXITCODE -eq 0) { "OK: $Drive -> $UNC" } else { throw "Failed to map $Drive to $UNC (code=$LASTEXITCODE)" }
