#requires -Version 5.1
[CmdletBinding()]
param(
  [string]$ProjectRoot = "D:\ester-project"
)

# UTF-8 for console output
try {
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
  [Console]::InputEncoding  = New-Object System.Text.UTF8Encoding($false)
  $OutputEncoding = [Console]::OutputEncoding
} catch {}

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$ProfilePs1  = Join-Path $ProjectRoot "tools\ester_profile.ps1"

function Pause-Here([string]$msg = "Enter - prodolzhit") {
  [void](Read-Host $msg)
}

function Run-Profile([string]$mode) {
  if (-not (Test-Path $ProfilePs1)) { throw "Ne nayden: $ProfilePs1" }
  & powershell -NoProfile -ExecutionPolicy Bypass -File $ProfilePs1 -Mode $mode -ProjectRoot $ProjectRoot
}

function Start-Py([string]$py) {
  $cmd = "Set-Location -LiteralPath '$ProjectRoot'; python $py"
  Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit","-ExecutionPolicy","Bypass","-Command",$cmd) | Out-Null
}

while ($true) {
  Clear-Host
  Write-Host "=== ESTER / PROFILI ===`n" -ForegroundColor Cyan

  Write-Host "1) DAY   (bystro/interaktivno)"
  Write-Host "2) NIGHT (gluboko/dolgo)"
  Write-Host "3) ETERNITY (6h taymauty + usilennyy kontekst)`n"

  Write-Host "4) STATUS   (pokazat aktivnye limity)"
  Write-Host "5) RESTORE  (otkat poslednego bekapa)`n"

  Write-Host "6) START app.py"
  Write-Host "7) START run_bot.py"
  Write-Host "8) START app.py + run_bot.py`n"

  Write-Host "0) Vykhod`n"

  $ch = Read-Host "Vybor"
  switch ($ch) {
    "1" { Run-Profile "day";      Pause-Here; continue }
    "2" { Run-Profile "night";    Pause-Here; continue }
    "3" { Run-Profile "eternity"; Pause-Here; continue }
    "4" { Run-Profile "status";   Pause-Here; continue }
    "5" { Run-Profile "restore";  Pause-Here; continue }
    "6" { Start-Py "app.py";      continue }
    "7" { Start-Py "run_bot.py";  continue }
    "8" { Start-Py "app.py"; Start-Py "run_bot.py"; continue }
    "0" { break }
    default { Write-Host "Nevernyy vybor." -ForegroundColor Yellow; Start-Sleep -Milliseconds 700 }
  }
}