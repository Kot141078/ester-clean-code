# R0/scripts/r0_auth_smoke.ps1 - smouk R0 dlya Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden) Janes - observations; Carpet&Thomas - minimizing uncertainty.
# Zemnoy abzats: odna knopka dlya bystroy proverki kontura /auth/auto → /admin.
# c=a+b

python tests/r0_auth_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r0_auth_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R0] Gotovo."
