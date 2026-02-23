# check_ester.ps1 - Smok-test dlya Owner
Write-Host "--- Zapusk diagnostiki Ester (Hardware: 2x 5060 Ti) ---" -ForegroundColor Cyan

# 1. Proverka kodirovki faylov (ischem povrezhdennye UTF-8)
$files = Get-ChildItem -Filter *.py -Recurse
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match "RїSЂR") { # Marker slomannoy kodirovki
        Write-Host "[!] OShIBKA: Bitye simvoly v fayle $($file.Name)" -ForegroundColor Red
    }
}

# 2. Proverka kriticheskikh putey
$paths = "memory", "state", "logs"
foreach ($p in $paths) {
    if (!(Test-Path $p)) {
        Write-Host "[?] VNIMANIE: Direktoriya $p otsutstvuet. Sozdayu..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $p | Out-Null
    }
}

# 3. Proverka VRAM (zaglushka dlya nvidia-smi)
Write-Host "[*] Proverka GPU..." -ForegroundColor Gray
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

Write-Host "--- Diagnostika zavershena ---" -ForegroundColor Green