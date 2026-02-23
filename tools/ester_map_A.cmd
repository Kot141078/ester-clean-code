@echo off
set SRV=DESKTOP-EA1PMNN
set SHR=LAN_SHARE
set USR=DESKTOP-EA1PMNN\lanuser
set PWD=Str0ngPass!
set DRV=Z:
for /f "tokens=3" %%i in ('net use %DRV% ^| find "%DRV%"') do set _state=ok
if "%_state%"=="" (
  cmdkey /add:%SRV% /user:%USR% /pass:%PWD%
  net use %DRV% \\%SRV%\%SHR% /persistent:yes
)
if exist %DRV%\nul exit /b 0
call "%~dp0ester_map_B.cmd"
exit /b %errorlevel%
