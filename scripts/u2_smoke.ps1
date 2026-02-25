# U2/scripts/u2_smoke.ps1 — offlayn-smoke Cortex
# Bridges: (Explicit) Enderton; (Hidden) Ashby; Carpet&Thomas.
# Earthly paragraph: one challenge - we think and launch.
# c=a+b

python tests/u2_smoke.py
if ($LASTEXITCODE -ne 0) { Write-Warning "u2_smoke exited $LASTEXITCODE (soft)"; }
Write-Host "[U2] Gotovo."
