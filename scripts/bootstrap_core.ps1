$ErrorActionPreference = "Stop"
$env:ESTER_ALIAS_MODE = "core"
if (-not $env:ESTER_STATE_DIR) {
  $stateBase = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA "Ester" } else { Join-Path $PWD "state" }
  $env:ESTER_STATE_DIR = Join-Path $stateBase "state"
}
if (-not $env:HOST) { $env:HOST = "127.0.0.1" }
if (-not $env:PORT) { $env:PORT = "8137" }

Write-Host "ESTER_ALIAS_MODE=$env:ESTER_ALIAS_MODE"
Write-Host "ESTER_STATE_DIR=$env:ESTER_STATE_DIR"
Write-Host "HOST=$env:HOST  PORT=$env:PORT"

powershell -NoLogo -ExecutionPolicy Bypass -File ".\scripts\ports_check.ps1" -Ports @($env:PORT,80,443,5000,8080) | Write-Host
powershell -NoLogo -ExecutionPolicy Bypass -File ".\scripts\win_make.ps1" dev-core
