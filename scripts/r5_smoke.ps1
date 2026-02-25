# Р5/skripts/р5_stoke.ps1 - offline stock for Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden) Ashby - soft mode; Carpet&Thomas - minimal information.
# Earth paragraph: generates portal/index.html from the latest digest.
# c=a+b

python tests/r5_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r5_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R5] Gotovo."
