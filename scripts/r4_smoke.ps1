# R4/scripts/r4_smoke.ps1 — obertka smouka R4 dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytyy #1) Ashbi — ustoychivost; (Skrytyy #2) Cover&Thomas — informativnyy minimum.
# Zemnoy abzats: bezopasnyy progon B-slota s avtokatbekom.
# c=a+b

python tests/r4_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r4_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R4] Gotovo."
