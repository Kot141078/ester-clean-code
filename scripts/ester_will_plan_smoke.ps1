param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

Write-Host "== WillPlanner :: /ester/will/plan =="

try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/will/plan") -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning ("GET /ester/will/plan failed: {0}" -f $_.Exception.Message)
}

Write-Host "== Done =="
