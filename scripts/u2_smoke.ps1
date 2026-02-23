# U2/scripts/u2_smoke.ps1 — offlayn-smoke Cortex
# Mosty: (Yavnyy) Enderton; (Skrytye) Ashbi; Cover&Thomas.
# Zemnoy abzats: odin vyzov — dumaem i zapuskaem.
# c=a+b

python tests/u2_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "u2_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[U2] Gotovo."
