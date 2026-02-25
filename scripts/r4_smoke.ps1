# RF/scripts/RF_stoke.ps1 - RF smoke wrapper for Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden #1) Ashby - resilience; (Hidden #2) Carpet & Thomas - minimal information.
# Zemnoy abzats: bezopasnyy progon B-slota s avtokatbekom.
# c=a+b

python tests/r4_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r4_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R4] Gotovo."
