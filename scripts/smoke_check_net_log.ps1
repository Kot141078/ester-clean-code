param (
    [switch]$ShowAll
)

$logPath = "$env:USERPROFILE\.ester\vstore\net_search_log.json"

if (-Not (Test-Path $logPath)) {
    Write-Error "Fallback log file not found: $logPath"
    exit 1
}

try {
    $lines = Get-Content $logPath -Encoding UTF8
    $found = $false
    foreach ($line in $lines) {
        $json = $line | ConvertFrom-Json -ErrorAction Stop
        if ($ShowAll) {
            Write-Host "[$($json.key)] $($json.answers | ConvertTo-Json -Compress)"
        }
        if ($json.key -eq "demo: sky color?") {
            Write-Host "Found fallback entry: $($json.answers | ConvertTo-Json -Compress)"
            $found = $true
        }
    }

    if (-not $found -and -not $ShowAll) {
        Write-Warning "Log exists but 'demo: sky color?' not found."
        exit 1
    }
} catch {
    Write-Error "Fallback log not valid JSONL: $_"
    exit 1
}
