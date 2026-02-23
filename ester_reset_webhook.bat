@echo off
setlocal
for /f "usebackq tokens=1* delims==" %%A in (`findstr /b "TELEGRAM_TOKEN=" "D:\ester-project\.env"`) do set TOKEN=%%B
if not defined TOKEN (
  echo TELEGRAM_TOKEN not found in .env
  exit /b 1
)
curl -s "https://api.telegram.org/bot%TOKEN%/deleteWebhook?drop_pending_updates=true"
echo.
endlocal
