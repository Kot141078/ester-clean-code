@echo off
chcp 65001 >nul
color 0A
cls
echo ===================================================
echo        ESTER CONTROL CENTER (NODE PRIMARY)
echo ===================================================
echo.
echo Select Operation Mode:
echo.
echo [1] SOCIAL MODE (Fast)
echo     - Context: 100 msgs
echo     - Memory:  10 facts
echo     - Tick:    60 sec
echo     - Best for: Chatting, Speed
echo.
echo [2] GOD MODE (Deep Thought 128k)
echo     - Context: 500 msgs (Massive)
echo     - Memory:  50 facts (Deep RAG)
echo     - Files:   100,000 chars (Full Books)
echo     - Tick:    180 sec (Slow Thinking)
echo     - Best for: Analysis, Sleeping, Evolution
echo.
echo ===================================================
set /p mode="Select Mode (1 or 2): "

if "%mode%"=="1" goto SOCIAL
if "%mode%"=="2" goto GOD
goto SOCIAL

:SOCIAL
echo.
echo >>> ACTIVATING SOCIAL MODE...
set ESTER_SCROLL_LIMIT=100
set ESTER_RAG_COUNT=10
set ESTER_MEM_CHARS=25000
set ESTER_FILE_CHARS=50000
set ESTER_TICK_INTERVAL=60
goto RUN

:GOD
echo.
echo >>> ACTIVATING GOD MODE (128K UNLEASHED)...
set ESTER_SCROLL_LIMIT=500
set ESTER_RAG_COUNT=50
set ESTER_MEM_CHARS=100000
set ESTER_FILE_CHARS=100000
set ESTER_TICK_INTERVAL=180
goto RUN

:RUN
echo.
echo [System] Launching Neural Core...
python run_ester_fixed.py
pause