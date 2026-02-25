param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

function Run-ScriptIfExists([string]$Path, [string]$Args = "") {
    if (Test-Path $Path) {
        Write-Host ("== Run {0} ==" -f $Path)
        try {
            & powershell -ExecutionPolicy Bypass -File $Path $Args
        } catch {
            Write-Warning ("{0} failed: {1}" -f $Path, $_.Exception.Message)
        }
    } else {
        Write-Host ("skip {0} (not found)" -f $Path)
    }
}

Write-Host "== Ester Full Suite :: base endpoints =="

# Basic checks directly
$paths = @(
    "/ester/thinking/manifest",
    "/ester/thinking/status",
    "/ester/thinking/quality_once",
    "/ester/will/status",
    "/ester/memory/status",
    "/ester/selfcheck",
    "/ester/sisters/status",
    "/ester/autonomy/map"
)

foreach ($p in $paths) {
    try {
        $method = "GET"
        $body = $null
        if ($p -eq "/ester/thinking/quality_once") {
            $method = "POST"
            $body = @{ prompt = "ester-full-suite-probe" } | ConvertTo-Json -Depth 6
        }

        if ($method -eq "GET") {
            $r = Invoke-WebRequest -Uri ($base + $p) -Method GET -UseBasicParsing -ErrorAction Stop
        } else {
            $r = Invoke-WebRequest -Uri ($base + $p) -Method POST -UseBasicParsing -ContentType "application/json" -Body $body -ErrorAction Stop
        }
        Write-Host ("{0} {1} -> {2}" -f $method, $p, $r.StatusCode)
    } catch {
        Write-Warning ("{0} failed: {1}" -f $p, $_.Exception.Message)
    }
}

Write-Host "== Ester Full Suite :: nested smoke scripts =="

Run-ScriptIfExists ".\scripts\ester_thinking_trace_smoke.ps1"
Run-ScriptIfExists ".\scripts\ester_memory_status_smoke.ps1"
Run-ScriptIfExists ".\scripts\ester_sisters_status_smoke.ps1"
Run-ScriptIfExists ".\scripts\ester_selfcheck_suite.ps1"

Write-Host "== Done =="
