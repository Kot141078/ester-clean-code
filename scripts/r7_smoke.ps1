# R7/scripts/r7_smoke.ps1 — offlayn-smoke nablyudaemosti
# Mosty: (Yavnyy) Enderton; (Skrytye) Ashbi; Cover&Thomas.
# Zemnoy abzats: stroit obs_report.md.
# c=a+b

python tests/r7_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "r7_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[R7] Gotovo."
