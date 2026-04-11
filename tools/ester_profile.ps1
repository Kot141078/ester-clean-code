#requires -Version 5.1
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet("day","night","eternity","status","restore")]
  [string]$Mode,
  [string]$ProjectRoot = "<repo-root>"
)

try {
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
  [Console]::InputEncoding  = New-Object System.Text.UTF8Encoding($false)
  $OutputEncoding = [Console]::OutputEncoding
} catch {}

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

$BackupRoot = Join-Path $ProjectRoot "tools\_backups"
New-Item -ItemType Directory -Force $BackupRoot | Out-Null

$envPath = Join-Path $ProjectRoot ".env"
$chatApi = Join-Path $ProjectRoot "modules\chat_api.py"

function New-Backup {
  $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $dst   = Join-Path $BackupRoot $stamp
  New-Item -ItemType Directory -Force $dst | Out-Null
  foreach ($p in @($envPath, $chatApi)) {
    if (Test-Path $p) { Copy-Item -Force $p (Join-Path $dst ([IO.Path]::GetFileName($p))) }
  }
  return $dst
}

function Restore-LastBackup {
  $last = Get-ChildItem $BackupRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1
  if (-not $last) { throw "Bekapov ne naydeno." }
  $envBak = Join-Path $last.FullName ".env"
  $apiBak = Join-Path $last.FullName "chat_api.py"
  if (Test-Path $envBak) { Copy-Item -Force $envBak $envPath }
  if (Test-Path $apiBak) { Copy-Item -Force $apiBak $chatApi }
  Write-Host "OK: vosstanovleno iz $($last.FullName)" -ForegroundColor Green
}

function Show-Status {
  Write-Host "=== STATUS ===" -ForegroundColor Cyan
  Write-Host "ProjectRoot: $ProjectRoot"
  Write-Host "ENV: $envPath"
  Write-Host "chat_api: $chatApi"
  if (Test-Path $envPath) {
    $lines = Get-Content $envPath -ErrorAction SilentlyContinue
    $pick = $lines | Where-Object { $_ -match '^(LLM_TIMEOUT|API_TIMEOUT|MAX_|CTX_|RAG_|WEB_)=' }
    if ($pick) { $pick | ForEach-Object { Write-Host $_ } } else { Write-Host "(v .env net yavnykh limitov)" }
  }
}

function Apply-Profile([hashtable]$changes) {
  $bak = New-Backup
  Write-Host "Backup: $bak" -ForegroundColor DarkGray
  $txt = (Test-Path $envPath) ? (Get-Content $envPath -Raw) : ""
  foreach ($k in $changes.Keys) {
    $v = $changes[$k]
    if ($txt -match "(?m)^$k=") { $txt = [regex]::Replace($txt, "(?m)^$k=.*$", "$k=$v") }
    else {
      if ($txt.Length -gt 0 -and -not $txt.EndsWith("`n")) { $txt += "`n" }
      $txt += "$k=$v`n"
    }
  }
  Set-Content -Path $envPath -Value $txt -Encoding UTF8
  Write-Host "OK: profil primenen (poka pravim tolko .env)." -ForegroundColor Green
}

switch ($Mode) {
  "status"   { Show-Status; break }
  "restore"  { Restore-LastBackup; break }
  "day"      { Apply-Profile @{ "LLM_TIMEOUT"="120";   "API_TIMEOUT"="120"   }; break }
  "night"    { Apply-Profile @{ "LLM_TIMEOUT"="3600";  "API_TIMEOUT"="3600"  }; break }
  "eternity" { Apply-Profile @{ "LLM_TIMEOUT"="21600"; "API_TIMEOUT"="21600" }; break }
}