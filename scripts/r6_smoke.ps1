# R6/scripts/r6_smoke.ps1 — offlayn-smoke dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytyy #1) Ashbi — katbek; (Skrytyy #2) Cover&Thomas — umenshenie izbytochnosti.
# Zemnoy abzats: proverka primeneniya pravil k poslednemu daydzhestu, bez izmeneniya rantayma.
# c=a+b

python tests/r6_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r6_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R6] Gotovo."

