echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM --- (skrytyy most: Ashby/homeostasis) rezhimy = raznye "ustavki" sistemy
REM --- (skrytyy most: Guyton/Hall) taymauty/kontekst kak "son/bodrstvovanie"
REM --- (skrytyy most: Enderton) pravka faylov tolko cherez proveryaemye pravila + otkat

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

:MENU
cls
echo === ESTER / PROFILI ===
echo.
echo 1) DAY       (bystro/interaktivno)
echo 2) NIGHT     (gluboko/dolgo)
echo 3) ETERNITY  (6h taymauty + rasshirennyy kontekst)
echo.
echo 4) STATUS    (pokazat aktivnye limity)
echo 5) RESTORE   (otkat poslednego bekapa)
echo.
echo 6) START app.py
echo 7) START run_bot.py
echo 8) START app.py + run_bot.py
echo.
echo 0) Vykhod
echo.
set /p CH=Vybor: 

if "%CH%"=="1" call :APPLY DAY 120 120 65000 120000 5000 & goto MENU
if "%CH%"=="2" call :APPLY NIGHT 3600 3600 85000 250000 10000 & goto MENU
if "%CH%"=="3" call :APPLY ETERNITY 21600 21600 110000 300000 15000 & goto MENU

if "%CH%"=="4" call :STATUS & pause & goto MENU
if "%CH%"=="5" call :RESTORE & pause & goto MENU

if "%CH%"=="6" call :START_APP & goto MENU
if "%CH%"=="7" call :START_BOT & goto MENU
if "%CH%"=="8" call :START_APP & call :START_BOT & goto MENU

if "%CH%"=="0" goto :EOF

echo Nevernyy vybor.
timeout /t 1 >nul
goto MENU


:APPLY
set "MODE=%~1"
set "LLM_TIMEOUT=%~2"
set "API_TIMEOUT=%~3"
set "SAFE_CHAR=%~4"
set "RAG_CHARS=%~5"
set "WEB_CHARS=%~6"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ErrorActionPreference='Stop';" ^
"$root='%ROOT%';" ^
"$envPath=Join-Path $root '.env';" ^
"$chatApi=Join-Path $root 'modules\chat_api.py';" ^
"$backupRoot=Join-Path $root 'tools\_backups';" ^
"New-Item -ItemType Directory -Force $backupRoot | Out-Null;" ^
"$stamp=(Get-Date -Format 'yyyyMMdd_HHmmss');" ^
"$dst=Join-Path $backupRoot $stamp; New-Item -ItemType Directory -Force $dst | Out-Null;" ^
"if(Test-Path $envPath){Copy-Item -Force $envPath (Join-Path $dst '.env')};" ^
"if(Test-Path $chatApi){Copy-Item -Force $chatApi (Join-Path $dst 'chat_api.py')};" ^
"$mode='%MODE%'; $llm=%LLM_TIMEOUT%; $api=%API_TIMEOUT%; $safe=%SAFE_CHAR%; $rag=%RAG_CHARS%; $web=%WEB_CHARS%;" ^
"$nl=[Environment]::NewLine;" ^
"function SetKV([string]$txt,[string]$k,[string]$v){" ^
"  $re='(?m)^'+[regex]::Escape($k)+'=.*$';" ^
"  if([regex]::IsMatch($txt,$re)){" ^
"    return [regex]::Replace($txt,$re,($k+'='+$v))" ^
"  } else {" ^
"    if($txt.Length -gt 0 -and -not $txt.EndsWith($nl)){ $txt += $nl }" ^
"    return $txt + ($k+'='+$v+$nl)" ^
"  }" ^
"}" ^
"$t=(Test-Path $envPath) ? (Get-Content $envPath -Raw) : '';" ^
"$t=SetKV $t 'ESTER_PROFILE' $mode;" ^
"$t=SetKV $t 'LLM_TIMEOUT' $llm;" ^
"$t=SetKV $t 'API_TIMEOUT' $api;" ^
"$t=SetKV $t 'ESTER_SAFE_CHAR_LIMIT' $safe;" ^
"$t=SetKV $t 'ESTER_MAX_RAG_CHARS' $rag;" ^
"$t=SetKV $t 'ESTER_MAX_WEB_CHARS' $web;" ^
"Set-Content -Path $envPath -Value $t -Encoding utf8;" ^
"if(Test-Path $chatApi){" ^
"  $py=Get-Content $chatApi -Raw;" ^
"  if($py -notmatch 'ESTER_SAFE_CHAR_LIMIT'){" ^
"    $py=[regex]::Replace($py,'(?m)^SAFE_CHAR_LIMIT\s*=\s*\d+\s*$','SAFE_CHAR_LIMIT = int(os.getenv(''ESTER_SAFE_CHAR_LIMIT'', ''85000''))');" ^
"    $py=[regex]::Replace($py,'(?m)^MAX_RAG_CHARS\s*=\s*\d+\s*$','MAX_RAG_CHARS = int(os.getenv(''ESTER_MAX_RAG_CHARS'', ''300000''))');" ^
"    $py=[regex]::Replace($py,'(?m)^MAX_WEB_CHARS\s*=\s*\d+\s*$','MAX_WEB_CHARS = int(os.getenv(''ESTER_MAX_WEB_CHARS'', ''5000''))');" ^
"    Set-Content -Path $chatApi -Value $py -Encoding utf8;" ^
"  }" ^
"  try { & python -m py_compile $chatApi | Out-Null; if($LASTEXITCODE -ne 0){ throw 'py_compile failed' } } catch {" ^
"    Write-Host '⚠️  chat_api.py ne proshel kompilyatsiyu — otkat.' -ForegroundColor Yellow;" ^
"    if(Test-Path (Join-Path $dst '.env')){ Copy-Item -Force (Join-Path $dst '.env') $envPath }" ^
"    if(Test-Path (Join-Path $dst 'chat_api.py')){ Copy-Item -Force (Join-Path $dst 'chat_api.py') $chatApi }" ^
"    exit 1" ^
"  }" ^
"}" ^
"Write-Host ('✅ Profile primenen: '+$mode+' (backup '+$dst+')') -ForegroundColor Green;"

if errorlevel 1 (
  echo Oshibka primeneniya profilya. Otkat sdelan (sm. tools\_backups).
  pause
)
exit /b 0


:STATUS
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$root='%ROOT%'; $envPath=Join-Path $root '.env';" ^
"Write-Host '=== STATUS ===' -ForegroundColor Cyan;" ^
"Write-Host ('Project: ' + $root);" ^
"if(Test-Path $envPath){" ^
"  $lines=Get-Content $envPath;" ^
"  $pick=$lines | Where-Object { $_ -match '^(ESTER_PROFILE|LLM_TIMEOUT|API_TIMEOUT|ESTER_SAFE_CHAR_LIMIT|ESTER_MAX_RAG_CHARS|ESTER_MAX_WEB_CHARS)=' };" ^
"  if($pick){ $pick | ForEach-Object { Write-Host $_ } } else { Write-Host '(limity ne naydeny v .env)' }" ^
"} else { Write-Host 'Net .env' -ForegroundColor Yellow }"
exit /b 0


:RESTORE
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$ErrorActionPreference='Stop'; $root='%ROOT%';" ^
"$backupRoot=Join-Path $root 'tools\_backups';" ^
"$envPath=Join-Path $root '.env'; $chatApi=Join-Path $root 'modules\chat_api.py';" ^
"if(-not (Test-Path $backupRoot)){ throw ('Net papki bekapov: '+$backupRoot) }" ^
"$last=Get-ChildItem $backupRoot -Directory | Sort-Object Name -Descending | Select-Object -First 1;" ^
"if(-not $last){ throw 'Bekapov ne naydeno.' }" ^
"$envBak=Join-Path $last.FullName '.env'; $apiBak=Join-Path $last.FullName 'chat_api.py';" ^
"if(Test-Path $envBak){ Copy-Item -Force $envBak $envPath }" ^
"if(Test-Path $apiBak){ Copy-Item -Force $apiBak $chatApi }" ^
"Write-Host ('✅ RESTORE iz '+$last.FullName) -ForegroundColor Green;"
exit /b 0


:START_APP
start "Ester app.py" powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command "& { Set-Location -LiteralPath '%ROOT%'; python app.py }"
exit /b 0


:START_BOT
start "Ester run_bot.py" powershell -NoProfile -ExecutionPolicy Bypass -NoExit -Command "& { Set-Location -LiteralPath '%ROOT%'; python run_bot.py }"
exit /b 0
