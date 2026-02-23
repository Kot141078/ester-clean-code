param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

Write-Host "== MemoryStatusFix :: /ester/memory/status =="
try {
    $r = Invoke-WebRequest -Uri "$base/ester/memory/status" -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "Cannot GET /ester/memory/status: $($_.Exception.Message)"
}

Write-Host "== Done =="
