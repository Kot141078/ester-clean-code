param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

function Invoke-JsonGet {
    param(
        [Parameter(Mandatory = $true)][string]$Url
    )

    $client = New-Object System.Net.Http.HttpClient
    try {
        $response = $client.GetAsync($Url).Result
        $body = $response.Content.ReadAsStringAsync().Result

        return [PSCustomObject]@{
            StatusCode = [int]$response.StatusCode
            Ok         = $response.IsSuccessStatusCode
            BodyRaw    = $body
        }
    }
    finally {
        $client.Dispose()
    }
}

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][hashtable]$Body
    )

    $client = New-Object System.Net.Http.HttpClient
    try {
        $json = $Body | ConvertTo-Json -Depth 10
        $content = New-Object System.Net.Http.StringContent($json, [System.Text.Encoding]::UTF8, "application/json")

        $response = $client.PostAsync($Url, $content).Result
        $bodyText = $response.Content.ReadAsStringAsync().Result

        return [PSCustomObject]@{
            StatusCode = [int]$response.StatusCode
            Ok         = $response.IsSuccessStatusCode
            BodyRaw    = $bodyText
        }
    }
    finally {
        $client.Dispose()
    }
}

$base = "http://{0}:{1}" -f $Host, $Port

Write-Host "=== Ester chat API selfcheck ==="
Write-Host "Base URL: $base"

# 1) /chat/health
$healthUrl = "$base/chat/health"
try {
    $health = Invoke-JsonGet -Url $healthUrl
    Write-Host "GET $healthUrl -> $($health.StatusCode)"
}
catch {
    Write-Host "ERROR calling $healthUrl"
    Write-Host $_.Exception.Message
    exit 1
}

# 2) /chat/message
$messageUrl = "$base/chat/message"
$payload = @{
    message    = "ping from selfcheck_chat_api.ps1"
    session_id = "selfcheck"
}

try {
    $msg = Invoke-JsonPost -Url $messageUrl -Body $payload
    Write-Host "POST $messageUrl -> $($msg.StatusCode)"
}
catch {
    Write-Host "ERROR calling $messageUrl"
    Write-Host $_.Exception.Message
    exit 1
}

# 3) /ester/chat/message (optional, compatibility check)
$esterUrl = "$base/ester/chat/message"
try {
    $ester = Invoke-JsonPost -Url $esterUrl -Body $payload
    Write-Host "POST $esterUrl -> $($ester.StatusCode)"
}
catch {
    Write-Host "WARN: /ester/chat/message check failed"
    Write-Host $_.Exception.Message
}

if (-not $health.Ok -or -not $msg.Ok) {
    Write-Host "=== Selfcheck FAILED ==="
    exit 2
}

Write-Host "=== Selfcheck OK ==="
exit 0
