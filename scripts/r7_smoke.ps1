# Р7/skripts/р7_stoke.ps1 - offline stock observability
# Bridges: (Explicit) Enderton; (Hidden) Ashby; Carpet&Thomas.
# Zemnoy abzats: stroit obs_report.md.
# c=a+b

python tests/r7_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "r7_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[R7] Gotovo."
