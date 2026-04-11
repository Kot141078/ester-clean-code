# -*- coding: utf-8 -*-
param(
  [string]$GameDir = "<game-dir>"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$srcDir = Join-Path $root "tools\gta"
$srcCs  = Join-Path $srcDir "EsterGtaBridge.cs"
$srcTxt = Join-Path $srcDir "README_GTA_BRIDGE.txt"

if (!(Test-Path -LiteralPath $srcCs))  { throw "Missing source: $srcCs" }
if (!(Test-Path -LiteralPath $srcTxt)) { throw "Missing source: $srcTxt" }
if (!(Test-Path -LiteralPath $GameDir)) { throw "GameDir not found: $GameDir" }

$dstScripts = Join-Path $GameDir "scripts"
New-Item -ItemType Directory -Force -Path $dstScripts | Out-Null

$dstCs  = Join-Path $dstScripts "EsterGtaBridge.cs"
$dstTxt = Join-Path $GameDir "ESTER_GTA_BRIDGE_README.txt"

Copy-Item -LiteralPath $srcCs  -Destination $dstCs  -Force
Copy-Item -LiteralPath $srcTxt -Destination $dstTxt -Force

Write-Host "[OK] Installed:"
Write-Host "  $dstCs"
Write-Host "  $dstTxt"
Write-Host ""
Write-Host "Next:"
Write-Host "  1) Ensure ScriptHookV + ScriptHookVDotNet are installed in GTA folder."
Write-Host "  2) Start Ester backend (run_ester_fixed.py)."
Write-Host "  3) Start GTA V single-player."

