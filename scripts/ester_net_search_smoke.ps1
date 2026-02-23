param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

Write-Host "== NetSearch :: /ester/net/search as operator =="

$body = @{
    q = "test"
    limit = 2
    source = "operator"
} | ConvertTo-Json -Depth 6

try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/net/search") -Method POST -UseBasicParsing -ContentType "application/json" -Body $body
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning ("POST /ester/net/search failed: {0}" -f $_.Exception.Message)
}

Write-Host "== Done =="
