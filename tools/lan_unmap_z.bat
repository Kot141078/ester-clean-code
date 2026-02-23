@echo off
setlocal
set PS=PowerShell -NoProfile -ExecutionPolicy Bypass -File
%PS% "%~dp0\lan_unmap_z.ps1" %*
endlocal
