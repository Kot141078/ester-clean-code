$ErrorActionPreference = "Stop"
if (Test-Path ".\.env") { powershell -NoLogo -ExecutionPolicy Bypass -File ".\scripts\env_load.ps1" -EnvFile ".\.env" | Write-Host }
$env:ESTER_ALIAS_MODE = "core"
if (-not $env:HOST) { $env:HOST = "127.0.0.1" }
if (-not $env:PORT) { $env:PORT = "8137" }
Write-Host ">>> wsgi_secure.py   HOST=$env:HOST PORT=$env:PORT  (ESTER_ALIAS_MODE=$env:ESTER_ALIAS_MODE)"
python .\tools\bind_probe.py --host $env:HOST --port $env:PORT
python .\wsgi_secure.py
