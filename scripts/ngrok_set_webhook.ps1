#Requires -Version 5.1
param(
  [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

function Wait-NgrokPublicUrl {
  param([int]$Tries = 40, [int]$DelayMs = 500)
  for ($i=0; $i -lt $Tries; $i++) {
    try {
      $r = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 2
      $t = $r.tunnels | Where-Object { $_.proto -eq "https" }
      if ($t.public_url) { return $t.public_url }
    } catch { }
    Start-Sleep -Milliseconds $DelayMs
  }
  throw "Ne udalos poluchit public_url ot ngrok"
}

# 0) Peremennye iz okruzheniya
$TOKEN   = $env:TELEGRAM_BOT_TOKEN
if (-not $TOKEN) { throw "TELEGRAM_BOT_TOKEN ne zadan" }

$SECRET  = $env:TELEGRAM_WEBHOOK_SECRET
if (-not $SECRET) { $SECRET = "ester_webhook_secret_6151477055" } # safe default for test

$ALLOWED = $env:TELEGRAM_ALLOWED_UPDATES
if (-not $ALLOWED) { $ALLOWED = '["message","callback_query"]' }

# 1) Start ngrok (if it is not already running)
Write-Host "[INFO] Zapuskayu ngrok http $Port..."
$ng = Get-Process -Name "ngrok" -ErrorAction SilentlyContinue
if (-not $ng) {
  Start-Process -NoNewWindow -FilePath "$env:LOCALAPPDATA\Microsoft\WindowsApps\ngrok.exe" -ArgumentList "http $Port"
  Start-Sleep -Seconds 1
}

# 2) Zhdem URL
Write-Host "[INFO] Zhdu public_url ot ngrok..."
$PUBLIC = Wait-NgrokPublicUrl
Write-Host "[OK] Ngrok URL: $PUBLIC"

# 3) Local smoke check
$Base = "$PUBLIC/api/telegram/webhook"
Write-Host "[INFO] Smoke webhook GET/POST..."
try {
  $g = Invoke-WebRequest -UseBasicParsing -Uri $Base -Method GET
  if ($g.StatusCode -lt 200 -or $g.StatusCode -ge 300) { throw "GET non-2xx: $($g.StatusCode)" }
  $p = Invoke-WebRequest -UseBasicParsing -Uri $Base -Method POST -Headers @{ "X-Telegram-Bot-Api-Secret-Token" = $SECRET } -Body '{"ok":true}' -ContentType "application/json"
  if ($p.StatusCode -lt 200 -or $p.StatusCode -ge 300) { throw "POST non-2xx: $($p.StatusCode)" }
  Write-Host "[SMOKE] telegram_smoke_webhook zavershen uspeshno."
} catch {
  Write-Warning "SMOKE ne proshel: $_"
}

# 4) Register a webhock in Telegram (WITHOUT external Pothon modules)
Write-Host "[INFO] Registriruyu Telegram webhook: $Base"
$resp = Invoke-RestMethod -Uri "https://api.telegram.org/bot$TOKEN/setWebhook" -Method Post `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{
    url                  = $Base
    secret_token         = $SECRET
    allowed_updates      = $ALLOWED
    drop_pending_updates = "true"
  }

if ($resp.ok -and $resp.result -eq $true) {
  Write-Host "[DONE] Webhook zaregistrirovan."
} else {
  Write-Warning "setWebhook otvet: $(ConvertTo-Json $resp -Depth 6)"
}

Write-Host "[HINT] Panel ngrok: http://127.0.0.1:4040  (Inspect → smotri vkhodyaschie POST ot Telegram)"
