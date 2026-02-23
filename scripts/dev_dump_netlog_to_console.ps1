$logPath = "$env:USERPROFILE\.ester\vstore\net_search_log.json"

if (-Not (Test-Path $logPath)) {
    Write-Error "Fallback log file not found: $logPath"
    exit 1
}

try {
    $lines = Get-Content $logPath -Encoding UTF8
    foreach ($line in $lines) {
        try {
            $json = $line | ConvertFrom-Json -ErrorAction Stop
            Write-Host "• [$($json.key)]"
            $json.answers | ForEach-Object { Write-Host "  → $($_.id): $($_.text)" }
        } catch {
            Write-Warning "❗ Bad line skipped: $line"
        }
    }
} catch {
    Write-Error "Fallback log not valid JSONL: $_"
    exit 1
}
