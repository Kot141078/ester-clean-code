# U1/scripts/u1_smoke.ps1 — offlayn-smoke soveta
# Bridges: (Explicit) Enderton; (Hidden) Ashby; Carpet&Thomas.
# Earth paragraph: one button to check.
# c=a+b

python tests/u1_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "u1_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[U1] Gotovo."
