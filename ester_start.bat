@echo off
setlocal
set "REPO_WIN=%~dp0"
if "%REPO_WIN:~-1%"=="\" set "REPO_WIN=%REPO_WIN:~0,-1%"
set "ENV_FILE=%REPO_WIN%\\.env"
for /f "usebackq delims=" %%I in (`wsl.exe wslpath "%REPO_WIN%"`) do set "REPO_WSL=%%I"

set PORT=8010
set FLASK_DEBUG=0
set DEBUG=0

REM --- stopim staroe ---
wsl -e bash -lc "pkill -f serve_no_reload.py || true; pkill -f run_bot.sh || true"

REM --- bekend (novoe okno) ---
start "Ester Backend" wsl -e bash -lc "ESTER_REPO_ROOT=\"%REPO_WSL%\" PORT=%PORT% FLASK_DEBUG=%FLASK_DEBUG% DEBUG=%DEBUG% \"%REPO_WSL%/run_backend.sh\""

REM --- zhdem, poka podnimetsya health ---
powershell -NoProfile -Command "$e=0;1..40|%%{try{ iwr -UseBasicParsing http://127.0.0.1:%PORT%/health|Out-Null; exit 0 }catch{ Start-Sleep -Milliseconds 250 }}; exit 1" || goto :fail

REM --- ochischaem webhook i vklyuchaem bota ---
for /f "tokens=2 delims==" %%A in ('findstr /rc:"^TELEGRAM_TOKEN=" "%ENV_FILE%"') do set TELEGRAM_TOKEN=%%A
curl -s "https://api.telegram.org/bot%TELEGRAM_TOKEN%/deleteWebhook?drop_pending_updates=true" >NUL

start "Ester Telegram" wsl -e bash -lc "ESTER_REPO_ROOT=\"%REPO_WSL%\" \"%REPO_WSL%/run_bot.sh\""
exit /b 0

:fail
echo Backend didn't become healthy on port %PORT%.
exit /b 1
