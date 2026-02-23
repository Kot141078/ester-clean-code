Param([string]$Py = ".\.venv\Scripts\python.exe")
# Zapusk smoka iz lyubogo kataloga. Opredelyaem koren po raspolozheniyu etogo ps1:
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$Smoke = Join-Path $Root "tools\smoke_kompat_007.py"
& $Py $Smoke
