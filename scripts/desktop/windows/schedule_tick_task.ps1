# scripts\desktop\windows\schedule_tick_task.ps1
# Creates a Windows scheduled task that executes a tick every minute.
# Trebuet put k python.exe dostupnyy v PATH ili ukazhi polnyy put v $PythonExe.

param(
  [string]$PythonExe = "python",
  [string]$ProjectDir = "D:\ester-project"
)

$TaskName = "Ester_RPA_Tick"
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ProjectDir\bin\rpa_schedule_tick.py`""
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration ([TimeSpan]::MaxValue)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\ester" -LogonType S4U -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Description "Ester RPA tick every minute" -Force | Out-Null
Write-Host "Scheduled task '$TaskName' created."
