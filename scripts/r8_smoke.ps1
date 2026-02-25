# R8/scripts/r8_smoke.ps1 — offlayn-smoke bezopasnosti/reliza
# Bridges: (Explicit) Enderton; (Hidden) Ashby; Carpet&Thomas.
# Zemnoy abzats: gotovit sec_report.md i bundle.
# c=a+b

python tests/r8_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "r8_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[R8] Gotovo."
