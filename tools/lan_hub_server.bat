@echo off
setlocal
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0\lan_hub_server.ps1" %*
endlocal
