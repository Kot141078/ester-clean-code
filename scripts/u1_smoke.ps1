# U1/scripts/u1_smoke.ps1 — offlayn-smoke soveta
# Mosty: (Yavnyy) Enderton; (Skrytye) Ashbi; Cover&Thomas.
# Zemnoy abzats: odna knopka dlya proverki.
# c=a+b

python tests/u1_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "u1_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[U1] Gotovo."
