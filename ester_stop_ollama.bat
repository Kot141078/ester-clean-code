@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "PROJECT_DIR=%~dp0"
if not defined OLLAMA_HOME set "OLLAMA_HOME=%USERPROFILE%\Tools\ollama-portable"
set "OLLAMA_EXE=%OLLAMA_HOME%\ollama.exe"
set "MODEL_NAME=esther-qwen3-32b"
set "SHUTDOWN_SCRIPT=%PROJECT_DIR%tools\ollama_esther_shutdown.ps1"

echo [1/1] Stopping Esther core, proxy, and portable Ollama...
if not exist "%SHUTDOWN_SCRIPT%" (
  echo [ERR] Shutdown helper not found: %SHUTDOWN_SCRIPT%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SHUTDOWN_SCRIPT%" -ProjectDir "%PROJECT_DIR:~0,-1%" -OllamaExe "%OLLAMA_EXE%" -ModelName "%MODEL_NAME%"
if errorlevel 1 exit /b 1

echo Done.
exit /b 0
