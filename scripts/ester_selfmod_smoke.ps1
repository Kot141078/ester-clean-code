param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

Write-Host "== SelfMod :: /ester/selfmod/status =="
try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/selfmod/status") -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning ("GET /ester/selfmod/status failed: {0}" -f $_.Exception.Message)
}

Write-Host "== SelfMod :: dry-run /ester/selfmod/propose =="

$body = @{
    source = "ester"
    reason = "test_dry_run"
    changes = @(
        @{
            path = "modules/ester/sample_self_patch.py"
            content = "# sample self-generated file"
        }
    )
} | ConvertTo-Json -Depth 6

try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/selfmod/propose") -Method POST -UseBasicParsing -ContentType "application/json" -Body $body
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning ("POST /ester/selfmod/propose failed: {0}" -f $_.Exception.Message)
}

Write-Host "== Done =="
