param()

Write-Host "== SelfModWill :: /ester/selfmod/will_plan =="

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/ester/selfmod/will_plan" -UseBasicParsing -ErrorAction Stop
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "will_plan failed: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "== SelfModWill :: dry-run /ester/selfmod/propose_guarded (source=ester) =="

$body = @{
    source = "ester"
    reason = "dry_run_sample"
    changes = @(
        @{
            path    = "modules/ester/sample_self_patch_dryrun.py"
            content = "# ester: dry-run selfmod test`n"
        }
    )
} | ConvertTo-Json -Depth 6

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8080/ester/selfmod/propose_guarded" `
        -UseBasicParsing -Method POST -ContentType "application/json" -Body $body -ErrorAction Stop
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "propose_guarded dry-run failed: $($_.Exception.Message)"
}

Write-Host "== Done =="
