@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "PROJECT_DIR=%~dp0"
if not defined OLLAMA_HOME set "OLLAMA_HOME=%USERPROFILE%\Tools\ollama-portable"
set "OLLAMA_EXE=%OLLAMA_HOME%\ollama.exe"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"
set "PROXY_SCRIPT=%PROJECT_DIR%tools\ollama_openai_proxy.py"
set "MODEL_NAME=qwen2.5:32b"
set "BASE_MODEL=qwen2.5:32b"
set "VISION_MODEL=qwen2.5vl:7b"
set "MODELFILE="
set "OLLAMA_API=http://127.0.0.1:11434"
set "PROXY_API=http://127.0.0.1:1234"
set "BOOTSTRAP_SCRIPT=%PROJECT_DIR%tools\ollama_esther_bootstrap.ps1"

if not exist "%OLLAMA_EXE%" (
  echo [ERR] Ollama not found: %OLLAMA_EXE%
  exit /b 1
)

if not exist "%PYTHON_EXE%" (
  set "PYTHON_EXE=python"
)

if not exist "%BOOTSTRAP_SCRIPT%" (
  echo [ERR] Bootstrap helper not found: %BOOTSTRAP_SCRIPT%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%BOOTSTRAP_SCRIPT%" ^
  -ProjectDir "%PROJECT_DIR:~0,-1%" ^
  -OllamaExe "%OLLAMA_EXE%" ^
  -PythonExe "%PYTHON_EXE%" ^
  -ProxyScript "%PROXY_SCRIPT%" ^
  -ModelName "%MODEL_NAME%" ^
  -BaseModel "%BASE_MODEL%" ^
  -VisionModel "%VISION_MODEL%" ^
  -VisionPreload 1 ^
  -VisionKeepAlive "-1" ^
  -Modelfile "%MODELFILE%" ^
  -OllamaApi "%OLLAMA_API%" ^
  -ProxyApi "%PROXY_API%"
if errorlevel 1 exit /b 1

echo [6/6] Launching Esther with Ollama...
echo.
echo Esther is starting with Ollama.
echo Proxy:  %PROXY_API%
echo Ollama: %OLLAMA_API%
echo Model:  %MODEL_NAME%
echo Vision: %VISION_MODEL%
echo.
"%OLLAMA_EXE%" ps
echo.
echo Launching Esther core in this window...
set "LMSTUDIO_BASE_URL=%PROXY_API%/v1"
set "LMSTUDIO_API_KEY=ollama"
set "LMSTUDIO_MODEL=%MODEL_NAME%"
set "ESTER_CAPABILITY_PROFILE=local-multimodal-dual-gpu"
set "VISION_MODE=local"
set "VISION_MODEL=%VISION_MODEL%"
set "ESTER_VISION_PROVIDER=local"
set "ESTER_VISION_MODEL=%VISION_MODEL%"
set "ESTER_VISION_PRELOAD=1"
set "ESTER_VISION_KEEP_ALIVE=-1"
set "ESTER_VISION_MAX_TOKENS=1200"
set "LMSTUDIO_AUTO_MODEL=0"
set "LMSTUDIO_BASE=%PROXY_API%/v1"
set "LM_STUDIO_API_URL=%PROXY_API%/v1"
set "LM_STUDIO_API_KEY=ollama"
set "LM_STUDIO_MODEL=%MODEL_NAME%"
set "OLLAMA_BASE=%OLLAMA_API%"
set "OLLAMA_BASE_URL=%OLLAMA_API%"
set "OLLAMA_KEEP_ALIVE=30m"
set "OLLAMA_PROXY_DEFAULT_MODEL=%MODEL_NAME%"
set "OLLAMA_PROXY_TIMEOUT_SEC=1800"
set "LLM_DEFAULT_PROVIDER=ollama"
set "ESTER_FAST_PROVIDER=ollama"
set "ESTER_FAST_MODEL=%MODEL_NAME%"
set "ESTER_FAST_MAX_TOKENS=1800"
set "BROKER_MODEL_FALLBACK=%MODEL_NAME%"
set "GARAGE_LLM_PROVIDER=lmstudio"
powershell -ExecutionPolicy Bypass -File "%PROJECT_DIR%tools\run_ester_utf8.ps1" -EnableFlask 1
exit /b %errorlevel%
