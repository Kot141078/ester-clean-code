# scripts/ester_selfcheck_suite.ps1
# Integration self-chest stack Esther.

param(
    [string]$EsterHost = "127.0.0.1",
    [int]$EsterPort = 8080
)

$base = "http://$EsterHost`:$EsterPort"

function Ping([string]$Path, [string]$Method = "GET", $Body = $null) {
    try {
        if ($Method -eq "GET") {
            $r = Invoke-WebRequest -Uri ($base + $Path) -Method GET -UseBasicParsing
        } else {
            $json = $null
            if ($Body -ne $null) {
                $json = ($Body | ConvertTo-Json -Depth 6)
            }
            $r = Invoke-WebRequest -Uri ($base + $Path) -Method POST -UseBasicParsing -ContentType "application/json" -Body $json
        }
        Write-Host ("{0} {1} -> {2}" -f $Method, $Path, $r.StatusCode)
    } catch {
        Write-Warning ("{0} {1} failed: {2}" -f $Method, $Path, $_.Exception.Message)
    }
}

Write-Host "== EsterSelfCheck :: basic endpoints =="
Ping "/ester/thinking/manifest"
Ping "/ester/thinking/status"
Ping "/ester/will/status"
Ping "/ester/memory/status"
Ping "/ester/thinking/quality_once" "POST" @{ prompt = "selfcheck-quality-probe" }

Write-Host "== EsterSelfCheck :: unified /ester/selfcheck =="
try {
    $r = Invoke-WebRequest -Uri ($base + "/ester/selfcheck") -Method GET -UseBasicParsing
    Write-Host $r.StatusCode
    Write-Host $r.Content
} catch {
    Write-Warning "GET /ester/selfcheck failed: $($_.Exception.Message)"
}

Write-Host "== Done =="
