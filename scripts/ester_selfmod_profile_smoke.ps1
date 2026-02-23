param()

Write-Host "== SelfModProfile :: /ester/selfmod/profile =="

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/ester/selfmod/profile" -UseBasicParsing -ErrorAction Stop
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "/ester/selfmod/profile failed: $($_.Exception.Message)"
}

Write-Host "== Done =="
