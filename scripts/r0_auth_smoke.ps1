# R0/scripts/r0_auth_smoke.ps1 — smouk R0 dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytye) Dzheynes — nablyudeniya; Cover&Thomas — minimizatsiya neopredelennosti.
# Zemnoy abzats: odna knopka dlya bystroy proverki kontura /auth/auto → /admin.
# c=a+b

python tests/r0_auth_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r0_auth_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R0] Gotovo."
