@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "tools\add_extra_routes.ps1"
endlocal
