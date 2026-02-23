# R3/scripts/r3_smoke.ps1 — obertka smouka R3 dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytyy #1) Cover&Thomas — informativnyy minimum; (Skrytyy #2) Ashbi — prostaya regulyatsiya.
# Zemnoy abzats: build→score; myagkiy rezhim na pustykh dannykh.
# c=a+b

python tests/r3_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r3_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R3] Gotovo."
