# scripts\desktop\windows\ester_session.ps1
# Naznachenie: zapustit agent v seanse polzovatelya "ester" i uderzhivat ego zhivym.
param(
  [string]$User = "ester"
)

$ErrorActionPreference = "Stop"

# Proverka nalichiya agenta v aktivnom slote
$slot = (Get-Content "C:\Ester\releases\active.slot" -Encoding ASCII).Trim()
$agentPath = "C:\Ester\releases\$slot\ester_agent.ps1"
if (-not (Test-Path $agentPath)) {
  throw "Fayl agenta ne nayden: $agentPath"
}

Write-Host "==> Zapusk agenta iz slota $slot"

# VNIMANIE: RunAs zaprosit parol odin raz (sokhranite bezopasno).
$cmd = "powershell -ExecutionPolicy Bypass -NoLogo -NoProfile -File `"$agentPath`""
Start-Process -FilePath "runas.exe" -ArgumentList "/user:$env:COMPUTERNAME\$User `"$cmd`""

# Prostoy watchdog: zhdem podnyatiya health, inache pereklyuchaem slot
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
  Set-Content "C:\Ester\releases\active.slot" $new -Encoding ASCII
  $cmd2 = "powershell -ExecutionPolicy Bypass -NoLogo -NoProfile -File `"C:\Ester\releases\$new\ester_agent.ps1`""
  Start-Process -FilePath "runas.exe" -ArgumentList "/user:$env:COMPUTERNAME\$User `"$cmd2`""
  Write-Host "Pereklyucheno na slot $new."
}
