# PowerShell 5.x - Rollback patch
param(
  [Parameter(Mandatory=$true)]
  [string]$BackupDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = (Get-Location).Path

if (!(Test-Path -LiteralPath $BackupDir)) {
  throw "BackupDir ne nayden: $BackupDir"
}

Write-Host ">>> Restoring from $BackupDir" -ForegroundColor Cyan

$files = @(
  "telegram_adapter.py",
  "telegram_client.py",
  "run_ester_fixed.py",
  "chat_api.py"
)

foreach ($f in $files) {
  $src = Join-Path $BackupDir $f
  if (Test-Path -LiteralPath $src) {
    if ($f -eq "chat_api.py") {
      $dst = Join-Path $Root "modules\chat_api.py"
    } elseif ($f -eq "telegram_adapter.py") {
      $dst = Join-Path $Root "messaging\telegram_adapter.py"
    } elseif ($f -eq "telegram_client.py") {
      $dst = Join-Path $Root "modules\telegram_client.py"
    } else {
      $dst = Join-Path $Root $f
    }
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "restored: $dst" -ForegroundColor Green
  }
}

Write-Host ">>> ROLLBACK DONE" -ForegroundColor Cyan
