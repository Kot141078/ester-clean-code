@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\smoke_portal.ps1"
endlocal
