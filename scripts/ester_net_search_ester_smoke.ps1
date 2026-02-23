Param(
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

Write-Host "== NetSearchEster :: /ester/net/profile =="

try {
    $resp = Invoke-WebRequest -Uri "$BaseUrl/ester/net/profile" -UseBasicParsing -ErrorAction Stop
    Write-Host $resp.StatusCode
    Write-Host $resp.Content
} catch {
    Write-Warning "net/profile failed: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "== NetSearchEster :: /ester/net/search_logged_mem (operator) =="

$bodyOperator = @{
    q      = "Ester net_will bridge connectivity"
    limit  = 1
    source = "operator"
} | ConvertTo-Json -Depth 6

try {
    $resp = Invoke-WebRequest -Uri "$BaseUrl/ester/net/search_logged_mem" -Method POST -UseBasicParsing -ContentType "application/json" -Body $bodyOperator -ErrorAction Stop
    Write-Host $resp.StatusCode
    Write-Host $resp.Content
} catch {
    Write-Warning "operator search_logged_mem failed: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "== NetSearchEster :: /ester/net/search_logged_mem (ester) =="

$bodyEster = @{
    q      = "Ester self connectivity check"
    limit  = 1
    source = "ester"
} | ConvertTo-Json -Depth 6

try {
    $resp = Invoke-WebRequest -Uri "$BaseUrl/ester/net/search_logged_mem" -Method POST -UseBasicParsing -ContentType "application/json" -Body $bodyEster -ErrorAction Stop
    Write-Host $resp.StatusCode
    Write-Host $resp.Content
} catch {
    Write-Warning "ester search_logged_mem failed: $($_.Exception.Message)"
}

Write-Host "== Done =="
