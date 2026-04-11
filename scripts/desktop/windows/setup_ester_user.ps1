# scripts\desktop\windows\setup_ester_user.ps1
# Purpose: preparation of the "esther" user, directories, logs, A/V slots and basic configuration.
# Bezopasnye defolty, bez prav admina u ester.

param(
  [string]$User = "ester",
  [string]$BaseDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $BaseDir) {
  $BaseDir = if ($env:ProgramData) { Join-Path $env:ProgramData "Ester" } else { Join-Path $env:SystemDrive "Ester" }
}
$LogsDir = Join-Path $BaseDir "logs"
$ReleasesDir = Join-Path $BaseDir "releases"
$SlotA = Join-Path $ReleasesDir "A"
$SlotB = Join-Path $ReleasesDir "B"
$BinDir = Join-Path $BaseDir "bin"
$ActiveSlotFile = Join-Path $ReleasesDir "active.slot"
$HealthLog = Join-Path $LogsDir "health.jsonl"

Write-Host "==> Sozdanie lokalnogo polzovatelya $User (bez admin-prav)"
if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
  $Pass = Read-Host -AsSecureString "Set password for '$User'"
  New-LocalUser -Name $User -Password $Pass -FullName "Ester Service" -PasswordNeverExpires | Out-Null
  Add-LocalGroupMember -Group "Users" -Member $User
} else {
  Write-Host "Polzovatel uzhe suschestvuet, propuskayu."
}

Write-Host "==> Katalogi $BaseDir"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $SlotA | Out-Null
New-Item -ItemType Directory -Force -Path $SlotB | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

Write-Host "==> Fayl slota i health-flagi"
if (-not (Test-Path $ActiveSlotFile)) {
  Set-Content $ActiveSlotFile "A" -Encoding ASCII
}
if (-not (Test-Path $HealthLog)) {
  Set-Content $HealthLog "" -Encoding ASCII
}

Write-Host "==> Kopirovanie tekuschikh versiy agenta v sloty A/B (esli fayly uzhe est — propuskayu)"
$srcA = Join-Path $SlotA "ester_agent.ps1"
$srcB = Join-Path $SlotB "ester_agent.ps1"
if (-not (Test-Path $srcA)) { Copy-Item -Force "$PSScriptRoot\ester_agent.ps1" $srcA }
if (-not (Test-Path $srcB)) { Copy-Item -Force "$PSScriptRoot\ester_agent.ps1" $srcB }

Write-Host "==> Razreshaem RDP i multisessii (lokalnaya otladka)."
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop" | Out-Null

Write-Host "==> Gotovo."
