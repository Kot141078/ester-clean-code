# scripts\desktop\windows\ester_session.ps1
# Purpose: to launch the agent in the user session "esther" and keep it alive.
param(
  [string]$User = "ester",
  [string]$BaseDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $BaseDir) {
  $BaseDir = if ($env:ProgramData) { Join-Path $env:ProgramData "Ester" } else { Join-Path $env:SystemDrive "Ester" }
}
$ReleasesDir = Join-Path $BaseDir "releases"
$ActiveSlotFile = Join-Path $ReleasesDir "active.slot"

# Checking for an agent in the active slot
$slot = (Get-Content $ActiveSlotFile -Encoding ASCII).Trim()
$agentPath = Join-Path $ReleasesDir "$slot\ester_agent.ps1"
if (-not (Test-Path $agentPath)) {
  throw "Fayl agenta ne nayden: $agentPath"
}

Write-Host "==> Zapusk agenta iz slota $slot"

# ATTENTION: RunAs will ask for a password once (save it securely).
$cmd = "powershell -ExecutionPolicy Bypass -NoLogo -NoProfile -File `"$agentPath`""
Start-Process -FilePath "runas.exe" -ArgumentList "/user:$env:COMPUTERNAME\$User `"$cmd`""

# Simple watchdog: wait for the healthtn to be raised, otherwise switch the slot
$ok = $false
for ($i=0; $i -lt 20; $i++) {
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8732/health" -TimeoutSec 2
    if ($resp.StatusCode -eq 200 -and ($resp.Content -like '*"ok":true*')) { $ok = $true; break }
  } catch { Start-Sleep -Milliseconds 500 }
  Start-Sleep -Milliseconds 500
}

if (-not $ok) {
  Write-Host "Agent ne podnyalsya. Vypolnyayu avto-otkat."
  # Pereklyuchenie A<->B i povtor
  $new = if ($slot -eq 'A') { 'B' } else { 'A' }
  Set-Content $ActiveSlotFile $new -Encoding ASCII
  $newAgentPath = Join-Path $ReleasesDir "$new\ester_agent.ps1"
  $cmd2 = "powershell -ExecutionPolicy Bypass -NoLogo -NoProfile -File `"$newAgentPath`""
  Start-Process -FilePath "runas.exe" -ArgumentList "/user:$env:COMPUTERNAME\$User `"$cmd2`""
  Write-Host "Pereklyucheno na slot $new."
}
