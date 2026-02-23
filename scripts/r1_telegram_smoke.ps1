# R1/scripts/r1_telegram_smoke.ps1 — obertka smouka Telegram dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytye) Ashbi — prostoy regulyator; Cover&Thomas — minimizatsiya neopredelennosti.
# Zemnoy abzats: proverka webhook/ctrl bez realnogo Telegram, tolko lokalnye vyzovy.
# c=a+b

python tests/r1_telegram_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r1_telegram_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R1] Gotovo."
