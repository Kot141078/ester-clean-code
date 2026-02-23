# -*- coding: utf-8 -*-
param(
  [string]$GameDir = "D:\Launcher\Grand Theft Auto V Enhanced",
  [string]$ProjectDir = "D:\ester-project"
)

$ErrorActionPreference = "Stop"

function Copy-IfExists([string]$Src, [string]$Dst) {
  if (Test-Path -LiteralPath $Src) {
    $dstDir = Split-Path -Parent $Dst
    if ($dstDir) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
    Copy-Item -LiteralPath $Src -Destination $Dst -Force
    Write-Host "[OK] $Src -> $Dst"
    return $true
  }
  Write-Host "[MISS] $Src"
  return $false
}

if (!(Test-Path -LiteralPath $GameDir)) {
  throw "GameDir not found: $GameDir"
}
if (!(Test-Path -LiteralPath $ProjectDir)) {
  throw "ProjectDir not found: $ProjectDir"
}

$runtimeDrop = Join-Path $ProjectDir "dist\gta_runtime_drop"
$bridgeDrop  = Join-Path $ProjectDir "dist\gta_bridge_drop"

# 1) Core ScriptHookV files (already prepared in dist/gta_runtime_drop)
Copy-IfExists (Join-Path $runtimeDrop "dinput8.dll")     (Join-Path $GameDir "dinput8.dll") | Out-Null
Copy-IfExists (Join-Path $runtimeDrop "ScriptHookV.dll") (Join-Path $GameDir "ScriptHookV.dll") | Out-Null
Copy-IfExists (Join-Path $runtimeDrop "NativeTrainer.asi") (Join-Path $GameDir "NativeTrainer.asi") | Out-Null

# 2) Ester bridge script
Copy-IfExists (Join-Path $bridgeDrop "scripts\EsterGtaBridge.cs") (Join-Path $GameDir "scripts\EsterGtaBridge.cs") | Out-Null
Copy-IfExists (Join-Path $bridgeDrop "ESTER_GTA_BRIDGE_README.txt") (Join-Path $GameDir "ESTER_GTA_BRIDGE_README.txt") | Out-Null

# 3) Optional: if user later places ScriptHookVDotNet files into dist/gta_runtime_drop
Copy-IfExists (Join-Path $runtimeDrop "ScriptHookVDotNet.asi")  (Join-Path $GameDir "ScriptHookVDotNet.asi") | Out-Null
Copy-IfExists (Join-Path $runtimeDrop "ScriptHookVDotNet2.dll") (Join-Path $GameDir "ScriptHookVDotNet2.dll") | Out-Null
Copy-IfExists (Join-Path $runtimeDrop "ScriptHookVDotNet3.dll") (Join-Path $GameDir "ScriptHookVDotNet3.dll") | Out-Null

Write-Host ""
Write-Host "=== VERIFY ==="
$need = @(
  "dinput8.dll",
  "ScriptHookV.dll",
  "ScriptHookVDotNet.asi",
  "ScriptHookVDotNet2.dll",
  "ScriptHookVDotNet3.dll",
  "scripts\EsterGtaBridge.cs"
)
foreach ($n in $need) {
  $p = Join-Path $GameDir $n
  if (Test-Path -LiteralPath $p) {
    Write-Host ("[OK] " + $n)
  } else {
    Write-Host ("[MISSING] " + $n)
  }
}

Write-Host ""
Write-Host "Done."

