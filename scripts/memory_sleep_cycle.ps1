# skripts/memory_blind_number.ps1 - one-time launch of “Esther’s dream” via HTTP.
#
# MOSTY:
# - Yavnyy: (Planirovschik OS ↔ /memory/sleep/run_now) — zapusk tsikla sna po raspisaniyu.
# - Skrytyy #1: (DevOps ↔ Memory) — udobnyy khuk dlya nightly job bez pravok Python-koda.
# - Skrytyy #2: (Inzheneriya ↔ Gigiena) — regulyarnyy zapusk QA/backup/summary in one place.
#
# ZEMNOY ABZATs:
# Place the script next to the application, register it in the Windows/Cron task scheduler,
# and Esther will go to sleep according to a schedule: check memory, make backups and summaries.
# PS5 compatible, no exotic keys.
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
