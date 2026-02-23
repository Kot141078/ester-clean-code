# scripts/smoke_p2p.ps1 — dymovoy test P2P-mekhanizma (podpis i API) dlya PowerShell.

<#
Rezhimy:
  -Mode simple: Proveryaet podpis odnogo zaprosa (kak v legacy).
  -Mode full: Testiruet API (/p2p/bloom/status, /export, /merge).

Primery:
  $env:ESTER_P2P_SECRET="abc"; .\smoke_p2p.ps1 -Mode simple
  $env:BASE_URL="http://localhost:5000"; $env:ESTER_P2P_SECRET="abc"; .\smoke_p2p.ps1 -Mode full
  $env:P2P_SIG_LEGACY=1; $env:ESTER_P2P_SECRET="abc"; .\smoke_p2p.ps1 -Mode simple -PathPart /p2p/self/manifest/__smoke__

Mosty:
- Yavnyy (Windows ↔ P2P API): PowerShell-ekvivalent Bash-smouka.
- Skrytyy #1 (Dev-noutbuki ↔ Server): odinakovyy stsenariy na Win i *nix.
- Skrytyy #2 (CI ↔ Ops): podkhodit dlya self-hosted runner na Windows, JSON-otchet.

Zemnoy abzats:
Kak kontrolnaya lampa: v rezhime simple proveryaet podpis, v full — vsyu tsepochku API. Vse chetko, s otchetom dlya CI.

c=a+b
#>

$ErrorActionPreference = "Stop"

# Konfiguratsiya
param (
    [ValidateSet("simple", "full")][string]$Mode = "simple",
    [string]$PathPart = "/p2p/self/manifest/__smoke__",
    [string]$Method = "GET"
)

$BASE_URL = $env:BASE_URL
$HOST = $env:HOST
if ([string]::IsNullOrEmpty($HOST)) { $HOST = "127.0.0.1" }
$PORT = $env:PORT
if ([string]::IsNullOrEmpty($PORT)) { $PORT = "8080" }
if ([string]::IsNullOrEmpty($BASE_URL)) { $BASE_URL = "http://$HOST`:$PORT" }
$SECRET = $env:ESTER_P2P_SECRET
$P2P_SIG_LEGACY = $env:P2P_SIG_LEGACY
if ([string]::IsNullOrEmpty($P2P_SIG_LEGACY)) { $P2P_SIG_LEGACY = "0" }
if ([string]::IsNullOrEmpty($SECRET)) {
    Write-Host "[p2p-smoke] ERR: ESTER_P2P_SECRET is not set"
    exit 2
}

# Proverka zavisimostey
$python = "python"
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    Write-Host "[p2p-smoke] ERR: python not found"
    exit 2
}
if (-not (Test-Path "scripts/p2p_sign.py")) {
    Write-Host "[p2p-smoke] ERR: scripts/p2p_sign.py not found"
    exit 2
}

# Funktsiya dlya generatsii zagolovkov
function Gen-Hdrs([string]$method, [string]$path, [string]$body = "") {
    $args = @("scripts/p2p_sign.py", $method, $path, $body)
    if ($P2P_SIG_LEGACY -eq "1") { $args += "--secret"; $args += $SECRET }
    $out = & $python $args 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[p2p-smoke] ERR: header generation failed"
        exit $LASTEXITCODE
    }
    return $out
}

# Funktsiya dlya parsinga zagolovkov
function Parse-Headers([string]$line) {
    $pieces = $line -split "' " | ForEach-Object { $_.Trim("'") }
    $headers = @{}
    foreach ($h in $pieces) {
        $kv = $h -split ":\s*", 2
        if ($kv.Length -eq 2) { $headers[$kv[0]] = $kv[1] }
    }
    return $headers
}

# Funktsiya dlya vypolneniya HTTP-zaprosa
function Curl-H([string]$method, [string]$path, [string]$body = "") {
    $hdrs = Gen-Hdrs $method $path $body
    $headers = Parse-Headers $hdrs
    if ($body) { $headers["Content-Type"] = "application/json" }
    try {
        if (Get-Command "Invoke-WebRequest" -ErrorAction SilentlyContinue) {
            $resp = Invoke-WebRequest -Method $method -Uri ($BASE_URL + $path) -Headers $headers -Body $body -UseBasicParsing
            return @{ StatusCode = $resp.StatusCode; Content = $resp.Content }
        } else {
            $wc = New-Object Net.WebClient
            foreach ($k in $headers.Keys) { $wc.Headers.Add($k, $headers[$k]) }
            if ($body -and $method -eq "POST") { $wc.UploadString($BASE_URL + $path, $method, $body) | Out-Null }
            else { $wc.DownloadString($BASE_URL + $path) | Out-Null }
            return @{ StatusCode = 200; Content = "{}" }
        }
    } catch {
        $code = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
        return @{ StatusCode = $code; Content = "{}"; Error = $_.Exception.Message }
    }
}

# JSON-otchet
$report = @{
    ok = $true
    mode = $Mode
    tests = @()
}

# Funktsiya dlya dobavleniya rezultata testa
function Add-TestResult([string]$name, [int]$code, [string]$body, [string]$error = $null) {
    $test = @{
        name = $name
        code = $code
        ok = ($code -ge 200 -and $code -lt 300)
        body = $body
        error = $error
    }
    $script:report.tests += $test
}

# Rezhim simple
if ($Mode -eq "simple") {
    Write-Host "[p2p-smoke] Testing signature ($Method $PathPart)"
    $r = Curl-H $Method $PathPart
    $body_json = ($r.Content | ConvertFrom-Json -ErrorAction SilentlyContinue) ?? @{}
    $body_str = $r.Content
    if ($r.Error) { $body_str = "{}" }
    if ($r.StatusCode -eq 401) {
        Add-TestResult "signature" $r.StatusCode $body_str "unauthorized"
        Write-Host "[p2p-smoke] FAIL: 401 unauthorized"
    } else {
        Add-TestResult "signature" $r.StatusCode $body_str
        Write-Host "[p2p-smoke] PASS: code=$($r.StatusCode)"
    }
}

# Rezhim full
if ($Mode -eq "full") {
    # Test 1: status
    Write-Host "[p2p-smoke] 1) Testing /p2p/bloom/status"
    $r = Curl-H GET "/p2p/bloom/status"
    $body_json = ($r.Content | ConvertFrom-Json -ErrorAction SilentlyContinue) ?? @{}
    $body_str = $r.Content
    if ($r.Error) { $body_str = "{}" }
    if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 300) {
        Add-TestResult "status" $r.StatusCode $body_str "non-2xx code"
        Write-Host "[p2p-smoke] FAIL: status code=$($r.StatusCode)"
        $report.ok = $false
    } else {
        Add-TestResult "status" $r.StatusCode $body_str
        Write-Host "[p2p-smoke] PASS: status code=$($r.StatusCode)"
    }

    # Test 2: export
    Write-Host "[p2p-smoke] 2) Testing /p2p/bloom/export"
    $r = Curl-H GET "/p2p/bloom/export"
    $body_json = ($r.Content | ConvertFrom-Json -ErrorAction SilentlyContinue) ?? @{}
    $body_str = $r.Content
    if ($r.Error) { $body_str = "{}" }
    if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 300) {
        Add-TestResult "export" $r.StatusCode $body_str "non-2xx code"
        Write-Host "[p2p-smoke] FAIL: export code=$($r.StatusCode)"
        $report.ok = $false
        exit 1
    }
    Add-TestResult "export" $r.StatusCode $body_str
    $m = [int]($body_json.m ?? 0)
    $k = [int]($body_json.k ?? 0)
    $bits = [string]($body_json.bits_hex ?? "")
    $payload = @{ m = $m; k = $k; bits_hex = $bits } | ConvertTo-Json -Compress

    # Test 3: merge
    Write-Host "[p2p-smoke] 3) Testing /p2p/bloom/merge"
    $r = Curl-H POST "/p2p/bloom/merge" $payload
    $body_json = ($r.Content | ConvertFrom-Json -ErrorAction SilentlyContinue) ?? @{}
    $body_str = $r.Content
    if ($r.Error) { $body_str = "{}" }
    $ok = [bool]($body_json.ok ?? $false)
    if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 300 -or -not $ok) {
        Add-TestResult "merge" $r.StatusCode $body_str "non-2xx code or ok=false"
        Write-Host "[p2p-smoke] FAIL: merge code=$($r.StatusCode), ok=$ok"
        $report.ok = $false
        exit 1
    }
    Add-TestResult "merge" $r.StatusCode $body_str
    Write-Host "[p2p-smoke] PASS: merge code=$($r.StatusCode)"
}

# Vyvod JSON-otcheta
$report | ConvertTo-Json -Depth 4
if ($report.ok) {
    Write-Host "[p2p-smoke] OK"
    exit 0
} else {
    Write-Host "[p2p-smoke] FAILED"
    exit 1
}