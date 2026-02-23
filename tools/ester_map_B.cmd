@echo off
set SRV=DESKTOP-EA1PMNN
set SHR=LAN_SHARE
set USR=DESKTOP-EA1PMNN\lanuser
set PWD=Str0ngPass!
set DRV=Z:
net use %DRV% /delete /y >nul 2>nul
cmdkey /add:%SRV% /user:%USR% /pass:%PWD%
net use %DRV% \\%SRV%\%SHR% /persistent:yes
if exist %DRV%\nul exit /b 0
exit /b 1
