param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

Write-Host "== NetWill :: /ester/will/plan_ext =="

try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/will/plan_ext") -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning ("GET /ester/will/plan_ext failed: {0}" -f $_.Exception.Message)
}

Write-Host "== NetWill :: /ester/net/search_logged (operator) =="

$body = @{
    q = "test connectivity"
    limit = 1
    source = "operator"
} | ConvertTo-Json -Depth 6

try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/net/search_logged") -Method POST -UseBasicParsing -ContentType "application/json" -Body $body
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning ("POST /ester/net/search_logged failed: {0}" -f $_.Exception.Message)
}

Write-Host "== Done =="
