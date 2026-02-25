# P2/skripts/p2_ingest_stoke.ps1 - Smoke P2 wrapper for Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden) Ashby is a simple regulator; Carpet & Thomas - minimum observations.
# Zemnoy abzats: lokalnye fikstury, nikakoy seti.
# c=a+b

python tests/r2_ingest_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r2_ingest_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R2] Gotovo."
