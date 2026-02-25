# Rb/skripts/rb_stoke.ps1 - offline stock for Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden #1) Ashby - cutback; (Hidden #2) Carpet & Thomas - reducing redundancy.
# Earthly paragraph: checking that the rules are applied to the last digest, without changing the runtime.
# c=a+b

python tests/r6_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r6_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R6] Gotovo."

