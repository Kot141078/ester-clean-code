# S0/scripts/smoke_s0.ps1 — udobnyy smouk dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty proverok; (Skrytye) Ashbi — prostota regulyatora; Cover&Thomas — minimizatsiya "shuma" proverok.
# Zemnoy abzats: ne trogaet runtime; pomogaet bystro poymat grubye konflikty marshrutov i RBAC.
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
