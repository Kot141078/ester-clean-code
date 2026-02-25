<#
deploy/windows/install_ester_service.ps1 — ustanovka Ester kak Windows-servisa cherez NSSM

MOSTY:
- (Yavnyy) Stavit servis "Ester Service" s zapuskom uvicorn asgi.app_main:app.
- (Skrytyy #1) The parameters are read from .env (if you use dotenv, set the environment variables in the system “Advanced parameters”).
- (Skrytyy #2) Skript stavit NSSM pri otsutstvii (v %ProgramData%\nssm).

ZEMNOY ABZATs:
Pozvolyaet razvernut Ester kak klassicheskiy Windows-servis bez plyasok s pywin32. c=a+b
#>

param(
  [string]$ServiceName = "Ester Service",
  [string]$PythonExe = "C:\Python311\python.exe",
  [string]$WorkDir = "C:\ester",
  [string]$Host = "0.0.0.0",
  [int]$Port = 8080,
  [int]$Workers = 2,
  [string]$LogLevel = "info"
)

$ErrorActionPreference = "Stop"

function Ensure-NSSM {
  $nssmPath = "$env:ProgramData\nssm\nssm.exe"
  if (Test-Path $nssmPath) { return $nssmPath }
  Write-Host "NSSM not found, downloading..."
  $zip = "$env:TEMP\nssm.zip"
  Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zip
  Expand-Archive -Path $zip -DestinationPath "$env:ProgramData\nssm_content" -Force
  $candidate = Get-ChildItem "$env:ProgramData\nssm_content" -Recurse -Filter nssm.exe | Where-Object { $_.FullName -match "win64" } | Select-Object -First 1
  New-Item -ItemType Directory -Force -Path (Split-Path $nssmPath) | Out-Null
  Copy-Item $candidate.FullName $nssmPath -Force
  Remove-Item $zip -Force
  return $nssmPath
}

$nssm = Ensure-NSSM

# Sozdaem servis
& $nssm install "$ServiceName" $PythonExe "-m" "uvicorn" "asgi.app_main:app" "--host" $Host "--port" "$Port" "--workers" "$Workers" "--log-level" $LogLevel
& $nssm set "$ServiceName" AppDirectory $WorkDir
& $nssm set "$ServiceName" Start SERVICE_AUTO_START
& $nssm set "$ServiceName" AppStdout "$WorkDir\ester.out.log"
& $nssm set "$ServiceName" AppStderr "$WorkDir\ester.err.log"

Write-Host "Service '$ServiceName' installed. Starting..."
& $nssm start "$ServiceName"
Write-Host "Done."
