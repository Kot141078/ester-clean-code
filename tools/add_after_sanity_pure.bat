
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0add_after_sanity_pure.ps1"
if errorlevel 1 exit /b 1
