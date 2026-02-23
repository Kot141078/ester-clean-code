param()

Write-Host "=== Iter0 Net smoke ===" -ForegroundColor Cyan

# -------------------------------------------------------------
# 1. Zagruzka .env (esli est)
# -------------------------------------------------------------

$envPath = ".env"
if (Test-Path $envPath) {
    Write-Host "[env] loading from .env" -ForegroundColor DarkCyan
    foreach ($line in Get-Content -Path $envPath) {
        $trim = $line.Trim()
        if (-not $trim) { continue }
        if ($trim.StartsWith("#")) { continue }

        if ($trim -match '^\s*([^=\s]+)\s*=\s*(.*)\s*$') {
            $name = $matches[1]
            $value = $matches[2]

            if (-not [string]::IsNullOrWhiteSpace($name)) {
                # Ne pereopredelyaem uzhe zadannye peremennye protsessa
                if (-not (Get-Item -Path "Env:$name" -ErrorAction SilentlyContinue)) {
                    Set-Item -Path "Env:$name" -Value $value
                }
            }
        }
    }
} else {
    Write-Host "[env] .env not found, using current process env" -ForegroundColor DarkYellow
}

# -------------------------------------------------------------
# 2. Bazovye URL
# -------------------------------------------------------------

$BaseUrl = ($env:ESTER_BASE)
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = "http://127.0.0.1:8080"
}
$BaseUrl = $BaseUrl.TrimEnd("/")

$LmBase = ($env:LMSTUDIO_BASE_URL)
if ([string]::IsNullOrWhiteSpace($LmBase)) {
    $LmBase = "http://127.0.0.1:1234"
}
$LmBase = $LmBase.TrimEnd("/")

$LmModel = ($env:LMSTUDIO_MODEL)

Write-Host ("BaseUrl        : {0}" -f $BaseUrl) -ForegroundColor Gray
Write-Host ("LMStudio base  : {0}" -f $LmBase) -ForegroundColor Gray
if ([string]::IsNullOrWhiteSpace($LmModel)) {
    Write-Host "LM Studio model : (NE ZADAN, sm. LMSTUDIO_MODEL v .env)" -ForegroundColor DarkYellow
} else {
    Write-Host ("LM Studio model : {0}" -f $LmModel) -ForegroundColor Gray
}

# -------------------------------------------------------------
# 3. Khelpery
# -------------------------------------------------------------

function Invoke-JsonGet {
    param(
        [Parameter(Mandatory = $true)][string]$Url
    )

    try {
        Write-Host "GET $Url" -ForegroundColor DarkGray
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -Method GET -TimeoutSec 10
        Write-Host ("OK {0} : HTTP {1}" -f $Url, $r.StatusCode) -ForegroundColor Green
        return $r.Content
    } catch {
        Write-Host ("ERROR GET {0} : {1}" -f $Url, $_.Exception.Message) -ForegroundColor Red
        return $null
    }
}

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][hashtable]$Body
    )

    try {
        $json = $Body | ConvertTo-Json -Depth 6 -Compress
        Write-Host "POST $Url" -ForegroundColor DarkGray
        Write-Host "Body: $json" -ForegroundColor DarkGray

        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -Method POST -ContentType "application/json" -Body $json -TimeoutSec 30
        Write-Host ("OK {0} : HTTP {1}" -f $Url, $r.StatusCode) -ForegroundColor Green
        Write-Host $r.Content -ForegroundColor Gray
        return $r.Content
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode.Value__) {
            $code = $_.Exception.Response.StatusCode.Value__
            Write-Host ("ERROR POST {0} : HTTP {1}" -f $Url, $code) -ForegroundColor Red
        } else {
            Write-Host ("ERROR POST {0} : {1}" -f $Url, $_.Exception.Message) -ForegroundColor Red
        }
        if ($_.Exception.Response) {
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $respBody = $reader.ReadToEnd()
                if ($respBody) {
                    Write-Host $respBody -ForegroundColor DarkRed
                }
            } catch {
                # ignore
            }
        }
        return $null
    }
}

# -------------------------------------------------------------
# 4. Healthcheck / net-profile
# -------------------------------------------------------------

$healthUrl = "$BaseUrl/chat/health"
$healthContent = Invoke-JsonGet -Url $healthUrl
if ($healthContent) {
    try {
        $health = $healthContent | ConvertFrom-Json
        if ($health) {
            Write-Host ("health.version        = {0}" -f $health.version) -ForegroundColor DarkGray
            Write-Host ("health.providers      = {0}" -f ($health.providers -join ",")) -ForegroundColor DarkGray
            Write-Host ("health.net_autobridge = {0}" -f $health.net_autobridge) -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "WARN: cannot parse /chat/health JSON" -ForegroundColor DarkYellow
    }
}

$netProfileUrl = "$BaseUrl/ester/net/profile"
$netProfileContent = Invoke-JsonGet -Url $netProfileUrl
if ($netProfileContent) {
    try {
        $prof = $netProfileContent | ConvertFrom-Json
        if ($prof) {
            $cfg = $prof.config
            if (-not $cfg) { $cfg = $prof }
            Write-Host ("net.enabled       = {0}" -f $cfg.enabled) -ForegroundColor DarkGray
            Write-Host ("net.ester_allowed = {0}" -f $cfg.ester_allowed) -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "WARN: cannot parse /ester/net/profile JSON" -ForegroundColor DarkYellow
    }
}

# -------------------------------------------------------------
# 5. Ping LM Studio (optsionalno)
# -------------------------------------------------------------

if (-not [string]::IsNullOrWhiteSpace($LmModel)) {
    $lmUrl = "$LmBase/v1/chat/completions"
    $lmBody = @{
        model      = $LmModel
        messages   = @(@{ role = "user"; content = "Ester net-smoke: say 'ok'." })
        max_tokens = 32
    }
    $lmContent = Invoke-JsonPost -Url $lmUrl -Body $lmBody
    if ($lmContent) {
        try {
            $lm = $lmContent | ConvertFrom-Json
            if ($lm.choices -and $lm.choices[0].message.content) {
                Write-Host "LM Studio returned choices: OK" -ForegroundColor Green
            } else {
                Write-Host "LM Studio: no choices in response" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "WARN: cannot parse LM Studio JSON" -ForegroundColor DarkYellow
        }
    }
} else {
    Write-Host "Propusk LM Studio ping: LMSTUDIO_MODEL ne zadan." -ForegroundColor DarkYellow
}

# -------------------------------------------------------------
# 6. Testy /chat/message
# -------------------------------------------------------------

# Test 1: yavnyy zapros na internet
Write-Host ""
Write-Host "Test 1: explicit net request (net_test_1) ..." -ForegroundColor Cyan
$body1 = @{
    sid     = "net_test_1"
    mode    = "lmstudio"
    use_rag = $true
    message = "Ester, posmotri v internete aktualnye novosti pro RTX 5090 i kratko pereskazhi."
}
Invoke-JsonPost -Url "$BaseUrl/chat/message" -Body $body1 | Out-Null

# Test 2: neyavnyy, no setevoy (tseny)
Write-Host ""
Write-Host "Test 2: implicit net request (net_test_2) ..." -ForegroundColor Cyan
$body2 = @{
    sid     = "net_test_2"
    mode    = "lmstudio"
    use_rag = $true
    message = "Ester, kakie seychas aktualnye tseny na RTX 5090 v 2025 godu?"
}
Invoke-JsonPost -Url "$BaseUrl/chat/message" -Body $body2 | Out-Null

Write-Host ""
Write-Host "=== Iter0 Net smoke done ===" -ForegroundColor Cyan
