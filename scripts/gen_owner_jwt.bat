@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\gen_owner_jwt.ps1"
endlocal
