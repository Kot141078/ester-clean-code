Param(
  [string]$PythonExe = ".\.venv\Scripts\python.exe"
)
$ErrorActionPreference = "Stop"
Write-Host "[smoke] using" $PythonExe
& $PythonExe -V
& $PythonExe ".\tools\smoke_kompat_002.py"
