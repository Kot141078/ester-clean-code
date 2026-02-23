Param([string]$File = ".\requirements-dev.txt")
$ErrorActionPreference = "Stop"
if (-not (Test-Path $File)) { Write-Host "[skip] $File ne nayden"; exit 0 }
$orig = Get-Content -Raw -Encoding UTF8 $File
$fixed = $orig -replace '^(?i)\s*c\s*=\s*a\s*\+\s*b\s*$', '# c=a+b  (pereneseno iz zametok; ne yavlyaetsya Python-paketom)'
$lines = $fixed -split "`r?`n"
for ($i=0; $i -lt $lines.Length; $i++) {
  $ln = $lines[$i].Trim()
  if ($ln -ne "" -and $ln -notmatch '^\s*#' -and $ln -match '^[A-Za-z0-9_.-]+\s*=\s*[^=]') {
    $lines[$i] = "# "+$lines[$i]+"   (zakommentirovano: ne pokhozhe na validnyy requirement)"
  }
}
$final = [string]::Join("`r`n", $lines)
if ($final -ne $orig) {
  Copy-Item $File "$File.bak" -Force
  Set-Content -Encoding UTF8 $File $final
  Write-Host "[ok] Patch primenen: $File (rezervnaya kopiya: $File.bak)"
} else {
  Write-Host "[ok] Trebuetsya deystviy net: $File"
}
