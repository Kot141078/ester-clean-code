param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

Write-Host "== ThinkTrace :: /ester/thinking/manifest =="
try {
    $r = Invoke-WebRequest -Uri "$base/ester/thinking/manifest" -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
} catch {
    Write-Warning "Cannot GET /ester/thinking/manifest: $($_.Exception.Message)"
}

Write-Host "== ThinkTrace :: /ester/thinking/once =="
try {
    $body = @{ prompt = "Test kaskada dlya ThinkTrace." } | ConvertTo-Json -Depth 4
    $r = Invoke-WebRequest -Uri "$base/ester/thinking/once" -Method POST -UseBasicParsing -ContentType "application/json" -Body $body
    Write-Host $r.StatusCode
} catch {
    Write-Warning "Cannot POST /ester/thinking/once: $($_.Exception.Message)"
}

Write-Host "== ThinkTrace :: /ester/thinking/status =="
try {
    $r = Invoke-WebRequest -Uri "$base/ester/thinking/status" -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "Cannot GET /ester/thinking/status: $($_.Exception.Message)"
}

Write-Host "== Done =="
