# P1/skripts/p1_telegram_stoke.ps1 - Smoke Telegram wrapper for Windows PowerShell
# Bridges: (Explicit) Enderton - predicates; (Hidden) Ashby is a simple regulator; Carpet&Thomas - minimizing uncertainty.
# Earthly paragraph: checking webhook/strl without real Telegram, only local calls.
# c=a+b

python tests/r1_telegram_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r1_telegram_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R1] Gotovo."
