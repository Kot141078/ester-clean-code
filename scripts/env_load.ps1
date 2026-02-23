Param([string]$EnvFile = ".\.env")
$ErrorActionPreference = "Stop"
if (-not (Test-Path $EnvFile)) { Write-Host "[skip] .env ne nayden"; exit 0 }
Get-Content -Encoding UTF8 $EnvFile | ForEach-Object {
  $line = $_.Trim()
  if ($line -eq "" -or $line -match '^\s*#') { return }
  $kv = $line -split '=',2
  if ($kv.Length -eq 2) { $name=$kv[0].Trim(); $val=$kv[1]; [Environment]::SetEnvironmentVariable($name, $val, "Process"); Write-Host "[env] $name=$val" }
}
Write-Host "[ok] ENV peremennye zagruzheny v protsess"
