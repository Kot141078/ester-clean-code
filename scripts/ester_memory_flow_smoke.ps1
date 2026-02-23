param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)
$base = "http://$EsterHost`:$EsterPort"

Write-Host "== MemoryFlow :: /ester/thinking/manifest =="
try {
    $r = Invoke-WebRequest -Uri "$base/ester/thinking/manifest" -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
} catch {
    Write-Warning "Cannot GET /ester/thinking/manifest: $($_.Exception.Message)"
}

Write-Host "== MemoryFlow :: /ester/thinking/once test =="
try {
    $body = @{ prompt = "Kratkiy test myslitelnogo kaskada dlya MemoryFlow." } | ConvertTo-Json -Depth 4
    $r = Invoke-WebRequest -Uri "$base/ester/thinking/once" -Method POST -UseBasicParsing -ContentType "application/json" -Body $body
    Write-Host "Status:" $r.StatusCode
    if ($r.Headers["X-Ester-Memory-Recall"]) {
        Write-Host "X-Ester-Memory-Recall:" $r.Headers["X-Ester-Memory-Recall"]
    } else {
        Write-Host "X-Ester-Memory-Recall: <none> (ok)"
    }
} catch {
    Write-Warning "Cannot POST /ester/thinking/once: $($_.Exception.Message)"
}

Write-Host "== Done =="
