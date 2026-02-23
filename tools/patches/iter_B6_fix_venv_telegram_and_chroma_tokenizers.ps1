#requires -Version 5.1
<#
B6a: PS5-safe fix for ternary operator usage in iter_B6 script.
Makes backup + can rollback.
#>

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [switch]$Rollback
)

$ErrorActionPreference = "Stop"

function Write-Head($s){ Write-Host "`n== $s ==" -ForegroundColor Cyan }
function Write-Ok($s){ Write-Host "[OK] $s" -ForegroundColor Green }
function Write-Warn($s){ Write-Host "[WARN] $s" -ForegroundColor Yellow }
function Write-Fail($s){ Write-Host "[FAIL] $s" -ForegroundColor Red }

$proj = (Resolve-Path -LiteralPath $ProjectRoot).Path
$target = Join-Path $proj "tools\patches\iter_B6_fix_venv_telegram_and_chroma_tokenizers.ps1"
if(!(Test-Path -LiteralPath $target)){ throw "Not found: $target" }

$backupRoot = Join-Path $proj "tools\patches\_backups"
if(!(Test-Path -LiteralPath $backupRoot)){ New-Item -ItemType Directory -Path $backupRoot | Out-Null }
$bak = Join-Path $backupRoot ("B6a_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
if(!(Test-Path -LiteralPath $bak)){ New-Item -ItemType Directory -Path $bak | Out-Null }

$bakFile = Join-Path $bak "iter_B6_before.ps1"
if($Rollback){
  # rollback = restore last B6a backup if exists
  $dirs = Get-ChildItem -LiteralPath $backupRoot -Directory | Where-Object { $_.Name -like "B6a_*" } | Sort-Object Name -Descending
  if($dirs.Count -eq 0){ throw "No B6a backups found in $backupRoot" }
  $last = $dirs[0].FullName
  $src = Join-Path $last "iter_B6_before.ps1"
  if(!(Test-Path -LiteralPath $src)){ throw "Missing backup file: $src" }
  Copy-Item -LiteralPath $src -Destination $target -Force
  Write-Ok "Rollback done: restored $target from $src"
  exit 0
}

Write-Head "B6a APPLY"
Copy-Item -LiteralPath $target -Destination $bakFile -Force
Write-Ok "Backup: $bakFile"

# replace the PS7 ternary with PS5 if/else
$content = Get-Content -LiteralPath $target -Raw

$old = 'if($reqVer -ne ""){
  Write-Ok ("requests=" + $reqVer)
} else {
  Write-Ok "requests=n/a"
}'
$new = @'
if($reqVer -ne ""){
  Write-Ok ("requests=" + $reqVer)
} else {
  Write-Ok "requests=n/a"
}
'@

if($content -notmatch [regex]::Escape($old)){
  Write-Warn "Pattern not found. Nothing changed."
  Write-Host "Expected line:"
  Write-Host "  $old"
  Write-Host "You may have a different B6 file version."
  exit 0
}

$content = $content.Replace($old, $new)
Set-Content -LiteralPath $target -Value $content -Encoding UTF8

Write-Ok "Patched ternary -> if/else (PS5-safe)."
Write-Host "Re-run:"
Write-Host "  cd $proj"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\tools\patches\iter_B6_fix_venv_telegram_and_chroma_tokenizers.ps1"
Write-Host ""
Write-Host "Rollback B6a:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\tools\patches\iter_B6a_fix_ps5_ternary_bug.ps1 -Rollback"

