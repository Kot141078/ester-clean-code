# -*- coding: utf-8 -*-
param()

$ErrorActionPreference = "Continue"

Write-Host "=== WHEEL STACK ON (Thrustmaster) ==="

$svcNames = @("tmHInstall", "tmInstall")
foreach ($sn in $svcNames) {
  $svc = Get-Service -Name $sn -ErrorAction SilentlyContinue
  if ($null -eq $svc) {
    Write-Host "[MISS SVC] $sn"
    continue
  }

  try {
    Set-Service -Name $sn -StartupType Automatic -ErrorAction Stop
    Write-Host "[SET AUTO] $sn"
  } catch {
    Write-Host "[WARN] cannot set startup type for ${sn}: $($_.Exception.Message)"
  }

  try {
    Start-Service -Name $sn -ErrorAction Stop
    Write-Host "[STARTED SVC] $sn"
  } catch {
    Write-Host "[WARN] cannot start service ${sn}: $($_.Exception.Message)"
  }
}

Write-Host "Done."
