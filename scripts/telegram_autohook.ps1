# -*- powershell -*-
# Robust Telegram webhook setter: beret tokeny iz Env ili iz .env, nakhodit https ngrok i registriruet vebkhuk.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DotEnvValue([string]$Key) {
  $val = [Environment]::GetEnvironmentVariable($Key, "Process")
  if (-not $val) { $val = [Environment]::GetEnvironmentVariable($Key, "User") }
  if (-not $val) { $val = [Environment]::GetEnvironmentVariable($Key, "Machine") }
  if (-not $val -and (Test-Path ".env")) {
    $m = Select-String -Path ".env" -Pattern ("^\s*{0}\s*=(.+)$" -f [regex]::Escape($Key)) | Select-Object -First 1
    if ($m) { $val = $m.Matches[0].Groups[1].Value.Trim() }
  }
  return $val
}

$ngrokApi = Get-DotEnvValue "NGROK_API"
if (-not $ngrokApi) { $ngrokApi = "http://127.0.0.1:4040" }

$token  = Get-DotEnvValue "TELEGRAM_BOT_TOKEN"
$secret = Get-DotEnvValue "TELEGRAM_WEBHOOK_SECRET"
$path   = Get-DotEnvValue "TELEGRAM_WEBHOOK_PATH"
if (-not $path) { $path = "/api/telegram/webhook" }

if (-not $token)  { throw "TELEGRAM_BOT_TOKEN not found (Env or .env)" }
if (-not $secret) { throw "TELEGRAM_WEBHOOK_SECRET not found (Env or .env)" }

$pub = (iwr "$ngrokApi/api/tunnels" | ConvertFrom-Json).tunnels |
          Where-Object { $_.public_url -like "https://*" } |
          Select-Object -ExpandProperty public_url -First 1
if (-not $pub) { throw "No https ngrok tunnel found at $ngrokApi" }

$hookUrl = "$pub$path"
Write-Host "[INFO] Set webhook to: $hookUrl"
$resp = iwr -Method Post ("https://api.telegram.org/bot{0}/setWebhook?url={1}&secret_token={2}" -f $token,$hookUrl,$secret)
$resp.Content
Write-Host "[INFO] getWebhookInfo:"
(iwr ("https://api.telegram.org/bot{0}/getWebhookInfo" -f $token)).Content
