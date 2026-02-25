Param(
    [string]$BaseUrl = "http://localhost:8000"
)

# scripts/telegram_smoke_webhook.ps1
# PS5-compatible helper for checking Telegram webhook.

$BaseUrl = $BaseUrl.TrimEnd('/')

$pingUrl = "$BaseUrl/api/telegram/webhook"
Write-Host "[INFO] GET $pingUrl"
try {
    $resp = Invoke-WebRequest -Uri $pingUrl -Method GET -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -eq 200) {
        Write-Host "[OK] /api/telegram/webhook otvechaet 200."
    } else {
        Write-Host "[WARN] Kod:" $resp.StatusCode
    }
}
catch {
    Write-Host "[WARN] Ne udalos obratitsya k $pingUrl : $($_.Exception.Message)"
}

$secret = $env:TELEGRAM_WEBHOOK_SECRET
if (-not $secret) {
    $secret = $env:TELEGRAM_SECRET_TOKEN
}

$body = @{
    update_id = 999999998
    message   = @{
        message_id = 1
        date       = 0
        chat       = @{ id = 0; type = "private" }
        text       = "telegram_smoke_webhook_ps1"
    }
} | ConvertTo-Json -Depth 4

$headers = @{ "Content-Type" = "application/json" }
if ($secret) {
    $headers["X-Telegram-Bot-Api-Secret-Token"] = $secret
    Write-Host "[INFO] Ispolzuem X-Telegram-Bot-Api-Secret-Token."
}

$postUrl = "$BaseUrl/api/telegram/webhook"
Write-Host "[INFO] POST $postUrl"
try {
    $resp2 = Invoke-WebRequest -Uri $postUrl -Method POST -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 5
    if ($resp2.StatusCode -eq 200) {
        Write-Host "[OK] Webhook prinyal testovyy apdeyt (200)."
        Write-Host "[SMOKE] telegram_smoke_webhook.ps1 zavershen."
        exit 0
    } else {
        Write-Host "[WARN] Otvet webhook:" $resp2.StatusCode $resp2.Content
        exit 1
    }
}
catch {
    Write-Host "[WARN] Oshibka POST: $($_.Exception.Message)"
    exit 1
}
