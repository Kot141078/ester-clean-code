# C0/skripts/stoke_s0.ps1 - convenient smoke for Windows PowerShell
# Bridges: (Explicit) Enderton - check predicates; (Hidden) Ashby - simplicity of the regulator; Carpet&Thomas - minimizing the "noise" of inspections.
# Earthly paragraph: does not touch the rintite; helps to quickly catch gross conflicts between routes and RVACH.
# c=a+b

Write-Host "[S0] Python version:"
python -V

Write-Host "[S0] Verify routes:"
python tools/verify_routes.py
if ($LASTEXITCODE -ne 0) { Write-Warning "verify_routes vernul kod $LASTEXITCODE" }

Write-Host "[S0] Mint admin JWT:"
$token = python tools/jwt_mint.py --user "Owner" --role admin --ttl 600
$token | Out-File -FilePath "$env:TEMP\jwt.txt" -Encoding ASCII

Write-Host "[S0] Smoke via test_client:"
python tests/smoke_s0.py
if ($LASTEXITCODE -ne 0) { Write-Warning "smoke_s0 vernul kod $LASTEXITCODE" }

Write-Host "[S0] Done."
