@echo off
setlocal
set PS=PowerShell -NoProfile -ExecutionPolicy Bypass -File
%PS% "%~dp0\lan_map_z.ps1" %*
endlocal
