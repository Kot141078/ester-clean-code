# R8/scripts/r8_smoke.ps1 — offlayn-smoke bezopasnosti/reliza
# Mosty: (Yavnyy) Enderton; (Skrytye) Ashbi; Cover&Thomas.
# Zemnoy abzats: gotovit sec_report.md i bundle.
# c=a+b

python tests/r8_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "r8_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[R8] Gotovo."
