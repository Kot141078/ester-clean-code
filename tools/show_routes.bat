@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\show_routes.ps1"
endlocal
