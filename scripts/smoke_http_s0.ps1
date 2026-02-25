# S0/scripts/smoke_http_s0.ps1 — HTTP-smouk dlya Windows PowerShell
# Bridges: (Explicit) Enderton - predicate checks; (Hidden) Ashby is a simple regulator; Carpet&Thomas - reducing the "entropy" of the configuration.
# Earth paragraph: does not change the system, terminates softly if the service is unavailable.
# c=a+b

if (-not $env:BASE_URL) { $env:BASE_URL = "http://127.0.0.1:8080" }
if (-not $env:CHECK_MODE) { $env:CHECK_MODE = "permissive" }
if (-not $env:GENERATE_JWT) { $env:GENERATE_JWT = "1" }

Write-Host "[S0] ENV selfcheck:"
python tools/env_selfcheck.py
if ($LASTEXITCODE -ne 0) { Write-Warning "env_selfcheck vernul kod $LASTEXITCODE" }

Write-Host "[S0] HTTP-smoke:"
python tests/integration_s0_http.py
if ($LASTEXITCODE -ne 0) { Write-Warning "integration_s0_http vernul kod $LASTEXITCODE" }

Write-Host "[S0] OK."
