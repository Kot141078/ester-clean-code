Param([string]$Py = ".\.venv\Scripts\python.exe")
# Run a stock from any directory. We determine the root by the location of this ps1:
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$Smoke = Join-Path $Root "tools\smoke_kompat_007.py"
& $Py $Smoke
