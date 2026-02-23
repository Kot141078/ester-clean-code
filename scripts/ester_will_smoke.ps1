param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)
$base = "http://$EsterHost`:$EsterPort"
Write-Host "== Ester will/autonomy status =="
try {
    $r = Invoke-WebRequest -Uri "$base/ester/will/status" -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "Cannot GET /ester/will/status: $($_.Exception.Message)"
}
Write-Host "== Autonomy status (raw) =="
try {
    $r = Invoke-WebRequest -Uri "$base/autonomy/status" -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "Cannot GET /autonomy/status: $($_.Exception.Message)"
}
Write-Host "== Done =="
