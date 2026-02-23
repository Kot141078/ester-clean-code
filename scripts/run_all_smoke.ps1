# S0/scripts/run_all_smoke.ps1 — obertka edinogo progona smoukov dlya Windows PowerShell
# Mosty: (Yavnyy) Ashbi — prostoy regulyator; (Skrytye) Enderton — predikaty; Cover&Thomas — minimizatsiya neopredelennosti.
# Zemnoy abzats: udobnaya knopka zapuska; sozdaet routes.md i matrix.md, ne valit stend.
# c=a+b

python tools/run_all_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "run_all_smoke vernul kod $LASTEXITCODE (myagkiy rezhim, dopustimo)."
}
Write-Host "[run_all_smoke] Gotovo. Sm. routes.md i matrix.md (esli sgenerirovany)."
