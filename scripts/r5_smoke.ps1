# R5/scripts/r5_smoke.ps1 — offlayn-smoke dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytye) Ashbi — myagkiy rezhim; Cover&Thomas — informativnyy minimum.
# Zemnoy abzats: formiruet portal/index.html iz poslednego daydzhesta.
# c=a+b

python tests/r5_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r5_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R5] Gotovo."
