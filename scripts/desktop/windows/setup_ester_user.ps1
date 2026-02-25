# scripts\desktop\windows\setup_ester_user.ps1
# Purpose: preparation of the "esther" user, directories, logs, A/V slots and basic configuration.
# Bezopasnye defolty, bez prav admina u ester.

param(
  [string]$User = "ester"
)

$ErrorActionPreference = "Stop"

Write-Host "==> Sozdanie lokalnogo polzovatelya $User (bez admin-prav)"
if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
  $Pass = Read-Host -AsSecureString "Set password for '$User'"
  New-LocalUser -Name $User -Password $Pass -FullName "Ester Service" -PasswordNeverExpires | Out-Null
  Add-LocalGroupMember -Group "Users" -Member $User
} else {
  Write-Host "Polzovatel uzhe suschestvuet, propuskayu."
}

Write-Host "==> Katalogi C:\Ester\{logs,releases\A,releases\B,bin}"
New-Item -ItemType Directory -Force -Path "C:\Ester\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Ester\releases\A" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Ester\releases\B" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Ester\bin" | Out-Null

Write-Host "==> Fayl slota i health-flagi"
if (-not (Test-Path "C:\Ester\releases\active.slot")) {
  Set-Content "C:\Ester\releases\active.slot" "A" -Encoding ASCII
}
if (-not (Test-Path "C:\Ester\logs\health.jsonl")) {
  Set-Content "C:\Ester\logs\health.jsonl" "" -Encoding ASCII
}

Write-Host "==> Kopirovanie tekuschikh versiy agenta v sloty A/B (esli fayly uzhe est — propuskayu)"
$srcA = "C:\Ester\releases\A\ester_agent.ps1"
$srcB = "C:\Ester\releases\B\ester_agent.ps1"
if (-not (Test-Path $srcA)) { Copy-Item -Force "$PSScriptRoot\ester_agent.ps1" $srcA }
if (-not (Test-Path $srcB)) { Copy-Item -Force "$PSScriptRoot\ester_agent.ps1" $srcB }

Write-Host "==> Razreshaem RDP i multisessii (lokalnaya otladka)."
Set-ItemProperty -Path "HKLM:\System\CurrentControlSet\Control\Terminal Server" -Name "fDenyTSConnections" -Value 0
Enable-NetFirewallRule -DisplayGroup "Remote Desktop" | Out-Null

Write-Host "==> Gotovo."
