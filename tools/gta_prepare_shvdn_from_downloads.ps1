# -*- coding: utf-8 -*-
param(
  [string]$DownloadsDir = "$env:USERPROFILE\Downloads",
  [string]$ProjectDir = "D:\ester-project"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -LiteralPath $DownloadsDir)) {
  throw "DownloadsDir not found: $DownloadsDir"
}
if (!(Test-Path -LiteralPath $ProjectDir)) {
  throw "ProjectDir not found: $ProjectDir"
}

$drop = Join-Path $ProjectDir "dist\gta_runtime_drop"
$tmp  = Join-Path $ProjectDir "dist\_tmp_shvdn_extract"
New-Item -ItemType Directory -Force -Path $drop | Out-Null
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

$zip = Get-ChildItem -LiteralPath $DownloadsDir -Recurse -File -Filter *.zip -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match 'ScriptHookVDotNet|SHVDN' } |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if ($null -eq $zip) {
  Write-Host "[FAIL] SHVDN zip not found in $DownloadsDir"
  exit 2
}

Write-Host "[INFO] Using: $($zip.FullName)"
Expand-Archive -LiteralPath $zip.FullName -DestinationPath $tmp -Force

$need = @("ScriptHookVDotNet.asi", "ScriptHookVDotNet2.dll", "ScriptHookVDotNet3.dll")
foreach ($n in $need) {
  $hit = Get-ChildItem -LiteralPath $tmp -Recurse -File -Filter $n -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($hit) {
    Copy-Item -LiteralPath $hit.FullName -Destination (Join-Path $drop $n) -Force
    Write-Host "[OK] $n"
  } else {
    Write-Host "[MISS] $n"
  }
}

Write-Host ""
Write-Host "[DONE] dist files:"
Get-ChildItem -LiteralPath $drop | Select-Object Name,Length,LastWriteTime
