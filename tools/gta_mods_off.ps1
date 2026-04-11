# -*- coding: utf-8 -*-
param(
  [string]$GameDir = "<game-dir>"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $GameDir)) {
  throw "GameDir not found: $GameDir"
}

$targets = @(
  "dinput8.dll",
  "ScriptHookV.dll",
  "ScriptHookVDotNet.asi",
  "ScriptHookVDotNet2.dll",
  "ScriptHookVDotNet3.dll"
)

function Ensure-WriteAccess([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) { return }
  $me = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  try { takeown /F "$Path" | Out-Null } catch {}
  try { icacls "$Path" /grant:r "${me}:(F)" /C | Out-Null } catch {}
}

function Disable-Target([string]$RelativePath) {
  $active = Join-Path $GameDir $RelativePath
  $off = "$active.off"

  if ((Test-Path -LiteralPath $active) -and (Test-Path -LiteralPath $off)) {
    Write-Host "[SKIP] both exist (manual check needed): $RelativePath"
    return
  }

  if (Test-Path -LiteralPath $active) {
    Ensure-WriteAccess $active
    Rename-Item -LiteralPath $active -NewName ([System.IO.Path]::GetFileName($off)) -Force
    Write-Host "[OFF] $RelativePath"
    return
  }

  if (Test-Path -LiteralPath $off) {
    Write-Host "[OK] already OFF: $RelativePath"
    return
  }

  Write-Host "[MISS] $RelativePath"
}

Write-Host "=== GTA MODS OFF ==="
Write-Host "GameDir: $GameDir"
Write-Host ""

foreach ($t in $targets) {
  Disable-Target $t
}

Write-Host ""
Write-Host "Done."
