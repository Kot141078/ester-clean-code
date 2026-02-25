\
    $ErrorActionPreference = "Stop"
    if (Test-Path ".\.env") { powershell -NoLogo -ExecutionPolicy Bypass -File ".\scripts\env_load.ps1" -EnvFile ".\.env" | Write-Host }
    $env:ESTER_ALIAS_MODE = "core"
    # Preference FLASK_NOST/FLASK_PORT, otherwise FLASK_PORT, otherwise defaults
    $hostv = if ($env:FLASK_HOST) { $env:FLASK_HOST } elseif ($env:HOST) { $env:HOST } else { "127.0.0.1" }
    $portv = if ($env:FLASK_PORT) { $env:FLASK_PORT } elseif ($env:PORT) { $env:PORT } else { "8137" }
    Write-Host (">>> app.py   HOST={0} PORT={1}  (ESTER_ALIAS_MODE={2})" -f $hostv, $portv, $env:ESTER_ALIAS_MODE)
    python .\tools\bind_probe.py --host $hostv --port ([int]$portv)
    $env:FLASK_HOST = $hostv
    $env:FLASK_PORT = $portv
    python .\app.py
    # Mosty: PowerShell -> Python, ENV -> Flask
    # Earth paragraph: a single command to launch the kernel.
    # c=a+b
