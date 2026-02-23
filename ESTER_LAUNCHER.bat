@echo off
chcp 65001 >nul
title ESTER CONTROL CENTER (NODE: PRIMARY)
color 0b

REM ============================================================
REM ESTER_LAUNCHER.bat — tsentralizovannyy zapusk rezhimov (Core / UI / oba)
REM
REM YaVNYY MOST: c=a+b — vybor Owner (a) + protsedury zapuska (b) => rezhim raboty uzla (c).
REM SKRYTYE MOSTY:
REM   - Ashby (requisite variety): neskolko rezhimov zapuska = raznoobrazie, menshe “khrupkosti” sistemy.
REM   - Cover&Thomas (ogranichenie kanala): UI i Core na raznykh portakh/kanalakh, menshe konfliktov i “shumov”.
REM
REM ZEMNOY ABZATs (anatomiya/inzheneriya):
REM   Eto kak razvesti “serdtse” i “monitor”: serdtse kachaet (Core), monitor pokazyvaet (UI).
REM   Esli posadit oba na odin sosud (port 8080) — budet tromb (konflikt).
REM ============================================================

set "PROJECT_DIR=%~dp0"
pushd "%PROJECT_DIR%"

:menu
cls
echo ========================================================
echo        ESTER AI SYSTEM -- CONTROL INTERFACE
echo ========================================================
echo.
echo    [1] ZAPUSTIT ESTER (Core / Telegram / Brain)
echo        ^> run_ester_fixed.py  (PORT=8080)
echo.
echo    [2] ZAPUSTIT UI (Web Monitor ONLY)
echo        ^> app.py (UI-only, TG disabled)  (PORT=8081)
echo.
echo    [3] ZAPUSTIT CORE + UI (2 okna)
echo        ^> Core: 8080 ^| UI: 8081 ^| TG tolko v Core
echo.
echo    [4] VSPOMNIT SEBYa (Self-Ingest)
echo        ^> ingest_all.py
echo.
echo    [5] ISSLEDOVAT MIR (World Scanner)
echo        ^> world_scanner.py
echo.
echo    [6] MIGRATsIYa PAMYaTI (Legacy)
echo        ^> migrate_memory.py
echo.
echo    [9] PODSKAZKI (URL/porty/chto gde)
echo.
echo    [0] VYKhOD (Sleep)
echo.
echo ========================================================
set /p choice="Vasha Volya, Owner (vvedite nomer): "

if "%choice%"=="1" goto run_core
if "%choice%"=="2" goto run_ui
if "%choice%"=="3" goto run_both
if "%choice%"=="4" goto self_ingest
if "%choice%"=="5" goto world_scan
if "%choice%"=="6" goto migrate
if "%choice%"=="9" goto hints
if "%choice%"=="0" goto end

goto menu

:run_core
cls
echo [Zapusk] Core (run_ester_fixed.py) na portu 8080...
set "PORT=8080"
set "HOST=0.0.0.0"
REM TG v Core ostavlyaem kak est (token beretsya iz .env)
python run_ester_fixed.py
pause
goto menu

:run_ui
cls
echo [Zapusk] UI-only (app.py) na portu 8081...
echo         TG otklyuchaem v UI, chtoby ne bylo 409 Conflict.
set "PORT=8081"
set "HOST=127.0.0.1"
set "ESTER_UI_ONLY=1"
set "ESTER_TELEGRAM_ENABLED=0"
python app.py
pause
goto menu

:run_both
cls
echo [Zapusk] Core + UI (2 okna)...
echo   Core: http://127.0.0.1:8080
echo   UI  : http://127.0.0.1:8081
echo.

REM Core window
start "ESTER CORE (8080)" cmd /k ^
  "cd /d \"%PROJECT_DIR%\" && set PORT=8080 && set HOST=0.0.0.0 && python run_ester_fixed.py"

REM UI window (UI-only, TG disabled)
start "ESTER UI (8081)" cmd /k ^
  "cd /d \"%PROJECT_DIR%\" && set PORT=8081 && set HOST=127.0.0.1 && set ESTER_UI_ONLY=1 && set ESTER_TELEGRAM_ENABLED=0 && python app.py"

echo Okna zapuscheny.
echo Esli uvidish 409 Conflict po Telegram — znachit gde-to esche zhivet vtoroy bot-protsess.
pause
goto menu

:self_ingest
cls
echo [Memory] Ester izuchaet svoyu strukturu...
python ingest_all.py
pause
goto menu

:world_scan
cls
echo [Glaza] Ester smotrit vo vneshniy mir...
echo Zapusk umnogo skanera (propusk dublikatov vklyuchen).
python world_scanner.py
pause
goto menu

:migrate
cls
echo [Arkhiv] Podnyatie starykh arkhivov...
python migrate_memory.py
pause
goto menu

:hints
cls
echo ========================================================
echo PODSKAZKI
echo ========================================================
echo Core API: http://127.0.0.1:8080
echo UI     : http://127.0.0.1:8081
echo.
echo Esli Telegram rugaetsya 409 Conflict:
echo  - Zakroy lishnie okna s Python (run_ester_fixed/run_bot/telegram_bot)
echo  - Ili naydi/ubey zavisshiy python.exe po CommandLine (sm. PowerShell komandy nizhe)
echo ========================================================
echo.
echo PowerShell (admin ne nuzhen):
echo   Get-CimInstance Win32_Process -Filter "Name='python.exe'" ^| Select-Object ProcessId,CommandLine
echo   Stop-Process -Id ^<PID^> -Force
echo.
pause
goto menu

:end
popd
exit /b 0
