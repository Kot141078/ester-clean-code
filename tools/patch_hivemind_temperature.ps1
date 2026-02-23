param(
  [string]$Target = "D:\ester-project\run_ester_fixed.py"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $Target)) {
  throw "Target not found: $Target"
}

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$Target.bak_$ts"
Copy-Item -LiteralPath $Target -Destination $bak -Force
Write-Host "[OK] Backup created: $bak"

$src = Get-Content -LiteralPath $Target -Raw -Encoding UTF8

# A-slot: dobavit defolt temperature=0.7, esli on obyazatelnyy
# Ischem imenno signaturu, gde temperature bez '='
$patternA = 'def\s+_ask_provider\(\s*self\s*,\s*provider\s*,\s*messages\s*,\s*temperature\s*,'
$replA    = 'def _ask_provider(self, provider, messages, temperature=0.7,'

$patched = $src
if ($patched -match $patternA) {
  $patched = [regex]::Replace($patched, $patternA, $replA, 1)
  Write-Host "[OK] Patched signature: temperature=0.7"
} else {
  Write-Host "[WARN] Signature pattern not found (maybe already patched)."
}

# B-slot (neobyazatelnyy, no poleznyy): sdelat vyzov yavnym, esli on v tochnosti takoy
$patternB = 'self\._ask_provider\(\s*p\s*,\s*msgs\s*\)'
$replB    = 'self._ask_provider(p, msgs, temperature=0.7)'

if ($patched -match $patternB) {
  $patched = [regex]::Replace($patched, $patternB, $replB, 1)
  Write-Host "[OK] Patched call site: explicit temperature=0.7"
} else {
  Write-Host "[WARN] Call-site pattern not found (maybe different code or already patched)."
}

# Zapis obratno
Set-Content -LiteralPath $Target -Value $patched -Encoding UTF8
Write-Host "[OK] Written patched file: $Target"

# Bystraya proverka: kompilyatsiya
& "D:\ester-project\.venv\Scripts\python.exe" -m py_compile $Target
Write-Host "[OK] py_compile passed"

Write-Host ""
Write-Host "If something goes wrong, rollback:"
Write-Host "Copy-Item -LiteralPath `"$bak`" -Destination `"$Target`" -Force"
