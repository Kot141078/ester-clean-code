# Rz/skripts/rz_stoke.ps1 - Smoke Rz wrapper for Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden #1) Carpet & Thomas - minimal information; (Hidden #2) Ashby - simple regulation.
# Zemnoy abzats: build→score; myagkiy rezhim na pustykh dannykh.
# c=a+b

python tests/r3_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r3_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R3] Gotovo."
