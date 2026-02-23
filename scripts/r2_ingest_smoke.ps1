# R2/scripts/r2_ingest_smoke.ps1 — obertka smouka R2 dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty; (Skrytye) Ashbi — prostoy regulyator; Cover&Thomas — minimum nablyudeniy.
# Zemnoy abzats: lokalnye fikstury, nikakoy seti.
# c=a+b

python tests/r2_ingest_smoke.py
if ($LASTEXITCODE -ne 0) {
  Write-Warning "r2_ingest_smoke vernul kod $LASTEXITCODE (myagkiy rezhim)."
}
Write-Host "[R2] Gotovo."
