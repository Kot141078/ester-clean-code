# scripts/installers/install_usb_agent_windows_service.ps1
# Ustanovka Windows Service dlya agenta «odin vopros» (optsionalno).
# Trebuet prava administratora. Pytaetsya postavit pywin32; pri neuspekhe predlozhit Planirovschik zadach.

param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

function Have-Admin {
  $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Have-Admin)) {
  Write-Error "Zapustite PowerShell ot imeni administratora."
  exit 1
}

Write-Host "Proverka pywin32..."
try {
  & $PythonExe - <<'PY'
import importlib, sys
try:
    importlib.import_module('win32serviceutil')
    print('OK')
except Exception:
    print('MISS')
PY
  | Tee-Object -Variable pywin
} catch { $pywin = 'MISS' }

if ($pywin -notmatch 'OK') {
  Write-Host "Ustanavlivayu pywin32..."
  & $PythonExe -m pip install --upgrade pip
  & $PythonExe -m pip install pywin32
}

Write-Host "Registriruyu servis EsterUsbAgent..."
& $PythonExe windows\usb_agent_service.py install
& $PythonExe windows\usb_agent_service.py start

Write-Host "Gotovo. Proverka statusa:"
& sc.exe query EsterUsbAgent
# c=a+b
