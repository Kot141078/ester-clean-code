$ServerName = 'DESKTOP-EA1PMNN'
$ShareName  = 'LAN_SHARE'
$User       = "$ServerName\lanuser"
$Pass       = 'Str0ngPass!'      # change me
$Drive      = 'Z:'
$DataRoot   = 'Z:\ester-data'

# 1) Private profile + services
$iface = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1).InterfaceAlias
if ($iface) { Set-NetConnectionProfile -InterfaceAlias $iface -NetworkCategory Private }
foreach($s in 'FDResPub','fdPHost','SSDPSRV','upnphost','LanmanWorkstation'){
  Set-Service $s -StartupType Automatic -EA SilentlyContinue
  Start-Service $s -EA SilentlyContinue
}

# 2) Firewall (SMB canonical rules; ignore if absent)
Enable-NetFirewallRule -Name 'FPS-SMB-In-TCP','FPS-SMB-Out-TCP' -EA SilentlyContinue | Out-Null

# 3) Credentials (name and IP)
$ip = (Test-Connection -Count 1 $ServerName -EA SilentlyContinue).IPv4Address.IPAddressToString
cmdkey /add:$ServerName /user:$User /pass:$Pass | Out-Null
if ($ip) { cmdkey /add:$ip /user:$User /pass:$Pass | Out-Null }

# 4) Map drive
net use $Drive "\\$ServerName\$ShareName" /persistent:yes | Out-Null

# 5) Ester dirs + env
New-Item -ItemType Directory -Force -Path $DataRoot, "$DataRoot\inbox", "$DataRoot\snapshots" | Out-Null
setx PERSIST_DIR $DataRoot | Out-Null
setx DATA_DIR    $DataRoot | Out-Null

# 6) hosts pin (name -> current IP)
if ($ip) { Add-Content "$env:WINDIR\System32\drivers\etc\hosts" "`r`n$ip  $ServerName" }

# 7) A/B autoload of mapping at logon
$Tools = "C:\Tools"; New-Item -ItemType Directory -Force -Path $Tools | Out-Null
$A = Join-Path $Tools "ester_map_A.cmd"
$B = Join-Path $Tools "ester_map_B.cmd"

@"
@echo off
set SRV=$ServerName
set SHR=$ShareName
set USR=$User
set PWD=$Pass
set DRV=$Drive
for /f "tokens=3" %%i in ('net use %DRV% ^| find "%DRV%"') do set _state=ok
if "%_state%"=="" (
  cmdkey /add:%SRV% /user:%USR% /pass:%PWD%
  net use %DRV% \\%SRV%\%SHR% /persistent:yes
)
if exist %DRV%\nul exit /b 0
call "%~dp0ester_map_B.cmd"
exit /b %errorlevel%
"@ | Out-File -Encoding ASCII $A

@"
@echo off
set SRV=$ServerName
set SHR=$ShareName
set USR=$User
set PWD=$Pass
set DRV=$Drive
net use %DRV% /delete /y >nul 2>nul
cmdkey /add:%SRV% /user:%USR% /pass:%PWD%
net use %DRV% \\%SRV%\%SHR% /persistent:yes
if exist %DRV%\nul exit /b 0
exit /b 1
"@ | Out-File -Encoding ASCII $B

$Action  = New-ScheduledTaskAction -Execute $A
$Trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "Ester-MapDrive" -Action $Action -Trigger $Trigger -RunLevel Highest -Force | Out-Null

Write-Host "OK: $Drive -> \\$ServerName\$ShareName  DATA_DIR=$DataRoot"
