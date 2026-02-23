# S0/scripts/smoke_matrix.ps1 — Sbor matritsy statusov (Markdown) dlya Windows PowerShell
# Mosty: (Yavnyy) Enderton — predikaty statusov; (Skrytyy #1) Ashbi — prostoy regulyator; (Skrytyy #2) Dzheynes — nablyudeniya dlya pravdopodobiya «zdorovya».
# Zemnoy abzats: formiruet matrix.md bez vliyaniya na rantaym.
# c=a+b

if (-not $env:BASE_URL) { $env:BASE_URL = "http://127.0.0.1:8080" }
python tools/check_endpoints_matrix.py --endpoints tests/fixtures/endpoints.txt --out matrix.md
Write-Host "[smoke_matrix] Itog: matrix.md"
