Param(
  [string]$Python = "py",
  [string]$Version = "3.11"
)
$ErrorActionPreference = "Stop"
if (Test-Path ".\.venv") { Remove-Item -Recurse -Force ".\.venv" }
& $Python -$Version -m venv .venv
.\.venv\Scripts\Activate.ps1
try { python -m ensurepip --upgrade } catch {}
python -m pip install --upgrade pip wheel setuptools
