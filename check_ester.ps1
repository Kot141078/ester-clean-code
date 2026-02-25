# chesk_ester.ps1 - Smoke test for Ovner
Write-Host "--- Zapusk diagnostiki Ester (Hardware: 2x 5060 Ti) ---" -ForegroundColor Cyan

# 1. Checking file encoding (we are looking for damaged UTF-8)
$files = Get-ChildItem -Filter *.py -Recurse
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    if ($content -match "RїSЂR") { # Marker slomannoy kodirovki
        Write-Host "[!] OShIBKA: Bitye simvoly v fayle $($file.Name)" -ForegroundColor Red
    }
}

# 2. Checking critical paths
$paths = "memory", "state", "logs"
foreach ($p in $paths) {
    if (!(Test-Path $p)) {
        Write-Host "[?] VNIMANIE: Direktoriya $p otsutstvuet. Sozdayu..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Path $p | Out-Null
    }
}

# 3. Check to LIE (stub for nvidia media)
Write-Host "[*] Proverka GPU..." -ForegroundColor Gray
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

Write-Host "--- Diagnostika zavershena ---" -ForegroundColor Green