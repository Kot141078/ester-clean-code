@echo off
REM Obertka, chtoby vyzyvat kak `make` iz PowerShell/CMD.
setlocal
set PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe
%PS% -NoLogo -ExecutionPolicy Bypass -File "%~dp0win_make.ps1" %*
endlocal
