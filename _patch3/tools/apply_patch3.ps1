\
#requires -Version 5.1
<#
Ester patch apply script (safe A/B with auto-rollback)

Usage (PowerShell):
  1) Expand-Archive .\ester_patch3.zip -DestinationPath .\_patch3
  2) cd <repo-root>
  3) PowerShell -ExecutionPolicy Bypass -File .\_patch3\tools\apply_patch3.ps1 -ProjectRoot "<repo-root>" -PatchRoot ".\_patch3"

What it does:
- creates timestamped backup of target files (Slot A)
- copies patched files (Slot B)
- runs quick compile/import checks
- on failure: restores from backup automatically
#>

param(
  [string]$ProjectRoot = (Get-Location).Path,
  [string]$PatchRoot = $PSScriptRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Copy-WithDirs([string]$src, [string]$dst) {
  $dstDir = Split-Path -Parent $dst
  if (!(Test-Path $dstDir)) { New-Item -ItemType Directory -Force -Path $dstDir | Out-Null }
  Copy-Item -Force $src $dst
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $ProjectRoot (".patch_backup_patch3_" + $stamp)
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

# Files to patch (relative to project root)
$files = @(
  "register_all.py",
  "hub.py",
  "modules\register_all.py",
  "modules\autoload_everything.py",
  "routes\register_all.py",
  "routes\messaging_register_all.py",
  "routes\admin_routes.py",
  "routes\telemetry_routes.py",
  "routes\tools_routes.py",
  "routes\file_routes.py",
  "routes\mission_routes.py",
  "routes\whatsapp_routes.py",
  "routes\chat_api_routes.py"
)

Write-Host "[patch3] ProjectRoot = $ProjectRoot"
Write-Host "[patch3] PatchRoot   = $PatchRoot"
Write-Host "[patch3] BackupRoot  = $backupRoot"
Write-Host ""

# Slot A: backup existing files (only if exist)
foreach ($rel in $files) {
  $dst = Join-Path $ProjectRoot $rel
  if (Test-Path $dst) {
    $bak = Join-Path $backupRoot $rel
    Copy-WithDirs $dst $bak
    Write-Host "[backup] $rel"
  }
}

try {
  # Slot B: copy patched files
  foreach ($rel in $files) {
    $src = Join-Path $PatchRoot $rel
    $dst = Join-Path $ProjectRoot $rel
    if (!(Test-Path $src)) {
      throw "Missing in patch: $rel ($src)"
    }
    Copy-WithDirs $src $dst
    Write-Host "[apply ] $rel"
  }

  Write-Host ""
  Write-Host "[check] py_compile ..."
  $py = "python"
  & $py -m py_compile (Join-Path $ProjectRoot "register_all.py") | Out-Null
  & $py -m py_compile (Join-Path $ProjectRoot "modules\register_all.py") | Out-Null
  & $py -m py_compile (Join-Path $ProjectRoot "routes\register_all.py") | Out-Null
  & $py -m py_compile (Join-Path $ProjectRoot "routes\messaging_register_all.py") | Out-Null

  Write-Host "[check] import symbols ..."
  & $py -c "from register_all import register_all_skills, register_all; print('OK register_all_skills:', callable(register_all_skills))" | Out-Null

  Write-Host ""
  Write-Host "[patch3] SUCCESS"
  Write-Host "Backup kept at: $backupRoot"
}
catch {
  Write-Host ""
  Write-Host "[patch3] ERROR -> auto-rollback" -ForegroundColor Yellow
  Write-Host $_.Exception.Message -ForegroundColor Yellow

  foreach ($rel in $files) {
    $bak = Join-Path $backupRoot $rel
    $dst = Join-Path $ProjectRoot $rel
    if (Test-Path $bak) {
      Copy-WithDirs $bak $dst
      Write-Host "[rbk  ] $rel"
    }
  }
  Write-Host ""
  Write-Host "[patch3] ROLLBACK DONE. Nothing changed permanently." -ForegroundColor Yellow
  throw
}
