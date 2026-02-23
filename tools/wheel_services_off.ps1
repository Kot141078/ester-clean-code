# -*- coding: utf-8 -*-
param()

$ErrorActionPreference = "Continue"

Write-Host "=== WHEEL STACK OFF (Thrustmaster) ==="

$procNames = @("WheelSetup")
foreach ($pn in $procNames) {
  Get-Process -Name $pn -ErrorAction SilentlyContinue | ForEach-Object {
    try {
      Stop-Process -Id $_.Id -Force -ErrorAction Stop
      Write-Host "[STOPPED PROC] $($_.ProcessName) pid=$($_.Id)"
    } catch {
      Write-Host "[WARN] cannot stop process ${pn}: $($_.Exception.Message)"
    }
  }
}

$svcNames = @("tmHInstall", "tmInstall")
foreach ($sn in $svcNames) {
  $svc = Get-Service -Name $sn -ErrorAction SilentlyContinue
  if ($null -eq $svc) {
    Write-Host "[MISS SVC] $sn"
    continue
  }

  try {
    if ($svc.Status -ne "Stopped") {
      Stop-Service -Name $sn -Force -ErrorAction Stop
      Write-Host "[STOPPED SVC] $sn"
    } else {
      Write-Host "[OK] already stopped: $sn"
    }
  } catch {
    Write-Host "[WARN] cannot stop service ${sn}: $($_.Exception.Message)"
  }

  try {
    Set-Service -Name $sn -StartupType Manual -ErrorAction Stop
    Write-Host "[SET MANUAL] $sn"
  } catch {
    Write-Host "[WARN] cannot set startup type for ${sn}: $($_.Exception.Message)"
  }
}

Write-Host "Done."
