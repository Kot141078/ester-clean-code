# C0/scripts/run_all_stoke.ps1 - wrapper for a single knock run for Windows PowerShell
# Bridges: (Explicit) Ashby - simple regulator; (Hidden) Enderton - predicates; Carpet&Thomas - minimizing uncertainty.
# Earth paragraph: convenient start button; creates rutes.md and matrix.md, does not knock down the stand.
# c=a+b

python tools/run_all_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "run_all_smoke vernul kod $LASTEXITCODE (myagkiy rezhim, dopustimo)."
}
Write-Host "[run_all_smoke] Gotovo. Sm. routes.md i matrix.md (esli sgenerirovany)."
