# scripts/memory_sleep_cycle.ps1 — odnokratnyy zapusk «sna Ester» cherez HTTP.
#
# MOSTY:
# - Yavnyy: (Planirovschik OS ↔ /memory/sleep/run_now) — zapusk tsikla sna po raspisaniyu.
# - Skrytyy #1: (DevOps ↔ Memory) — udobnyy khuk dlya nightly job bez pravok Python-koda.
# - Skrytyy #2: (Inzheneriya ↔ Gigiena) — regulyarnyy zapusk QA/backup/summary v odnom meste.
#
# ZEMNOY ABZATs:
# Polozhi skript ryadom s prilozheniem, propishi ego v planirovschike zadach Windows/cron,
# i Ester budet zasypat po raspisaniyu: proveryat pamyat, delat bekap i svodku.
# PS5-sovmestimo, bez ekzoticheskikh klyuchey.
#
# c=a+b

param(
    [string]$BaseUrl = $env:ESTER_BASE_URL
)

if (-not $BaseUrl -or $BaseUrl.Trim() -eq "") {
    $BaseUrl = "http://127.0.0.1:8000"
}

$uri = "$BaseUrl/memory/sleep/run_now"

try {
    $body = "{}"
    $resp = Invoke-WebRequest -Uri $uri -Method POST -ContentType "application/json" -Body $body -UseBasicParsing
    if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
        try {
            $json = $resp.Content | ConvertFrom-Json
            $json | ConvertTo-Json -Depth 6
        } catch {
            Write-Output $resp.Content
        }
    } else {
        Write-Error ("memory_sleep_cycle.ps1: HTTP " + $resp.StatusCode)
    }
}
catch {
    Write-Error ("memory_sleep_cycle.ps1: " + $_.Exception.Message)
}
