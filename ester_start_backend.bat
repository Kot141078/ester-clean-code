@echo off
setlocal
set "REPO_WIN=%~dp0"
if "%REPO_WIN:~-1%"=="\" set "REPO_WIN=%REPO_WIN:~0,-1%"
for /f "usebackq delims=" %%I in (`wsl.exe wslpath "%REPO_WIN%"`) do set "REPO_WSL=%%I"
wsl.exe -e bash -lc "ESTER_REPO_ROOT=\"%REPO_WSL%\" \"%REPO_WSL%/run_backend.sh\""
endlocal
