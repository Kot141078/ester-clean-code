@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\gen_owner_jwt_pure.ps1"
endlocal
