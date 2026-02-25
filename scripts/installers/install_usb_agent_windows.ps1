# scripts/installers/install_usb_agent_windows.ps1
# Registers agent autostart via Windows Task Scheduler (without external dependencies).

<#
Mosty:
- Yavnyy (Ekspluatatsiya ↔ Praktika): Planirovschik zadach stabilno rabotaet na lyuboy Windows.
- Skrytyy 1 (Nadezhnost ↔ Bezopasnost): minimalnye prava, perezapuski po raspisaniyu i pri logone.
- Skrytyy 2 (Inzheneriya ↔ UX): bez servisnykh obertok i pywin32 — chistyy PowerShell.

Zemnoy abzats:
Sluzhba Windows dlya Python trebuet spets-obertki. Planirovschik — nadezhnyy layfkhak:
startuet pri vkhode v sistemu i periodicheski, chtoby agent vsegda byl zhiv.
#>

param(
  [string]$PythonExe = "python",
  [int]$IntervalMinutes = 5
)

$ErrorActionPreference = "Stop"

$taskName = "EsterUsbAgent"
$scriptCmd = "$PythonExe -m listeners.usb_one_question_agent"
$trigger1 = New-ScheduledTaskTrigger -AtLogOn
$trigger2 = New-ScheduledTaskTrigger -Once (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) -RepetitionDuration ([TimeSpan]::MaxValue)
$action   = New-ScheduledTaskAction -Execute $PythonExe -Argument "-m listeners.usb_one_question_agent"
$principal = New-ScheduledTaskPrincipal -UserId "$env:UserName" -LogonType Interactive -RunLevel LeastPrivilege

try {
    if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($trigger1,$trigger2) -Principal $principal -Description "Ester USB One-Question Agent"
    Write-Host "Gotovo. Proverka: schtasks /Query /TN `"$taskName`""
} catch {
    Write-Error $_
    exit 1
}
# c=a+b
