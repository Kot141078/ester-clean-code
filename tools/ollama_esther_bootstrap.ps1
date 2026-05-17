param(
    [string]$ProjectDir = "",
    [string]$OllamaExe = "",
    [string]$PythonExe = "python",
    [string]$ProxyScript = "",
    [string]$ModelName = "qwen2.5:32b",
    [string]$BaseModel = "qwen2.5:32b",
    [string]$VisionModel = "",
    [int]$VisionPreload = 0,
    [string]$VisionKeepAlive = "-1",
    [string]$Modelfile = "",
    [string]$OllamaApi = "http://127.0.0.1:11434",
    [string]$ProxyApi = "http://127.0.0.1:1234"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if ([string]::IsNullOrWhiteSpace($OllamaExe)) {
    $OllamaExe = Join-Path $env:USERPROFILE "Tools\ollama-portable\ollama.exe"
}
if ([string]::IsNullOrWhiteSpace($ProxyScript)) {
    $ProxyScript = Join-Path $ProjectDir "tools\ollama_openai_proxy.py"
}
function Resolve-VenvBasePython {
    param(
        [string]$CandidatePython,
        [string]$ProjectDir
    )

    if ([string]::IsNullOrWhiteSpace($CandidatePython)) {
        return $CandidatePython
    }
    if ($CandidatePython -notlike "*\.venv\Scripts\python.exe") {
        return $CandidatePython
    }

    $venvCfg = Join-Path $ProjectDir ".venv\pyvenv.cfg"
    if (!(Test-Path -LiteralPath $venvCfg)) {
        return $CandidatePython
    }

    $homeLine = Get-Content -Path $venvCfg |
        Where-Object { $_ -match '^\s*home\s*=\s*(.+?)\s*$' } |
        Select-Object -First 1

    if (-not $homeLine) {
        return $CandidatePython
    }

    $pythonHome = (($homeLine -split "=", 2)[1]).Trim()
    $basePython = Join-Path $pythonHome "python.exe"
    if (Test-Path -LiteralPath $basePython) {
        return $basePython
    }

    return $CandidatePython
}

function Wait-HttpOk {
    param(
        [string]$Uri,
        [int]$TimeoutSec = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing $Uri -TimeoutSec 2
            if ($resp.StatusCode -eq 200) {
                return
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Endpoint did not become ready: $Uri"
}

$PythonExe = Resolve-VenvBasePython -CandidatePython $PythonExe -ProjectDir $ProjectDir

Write-Host "[1/5] Ensuring Ollama server is running..."
try {
    Wait-HttpOk -Uri "$OllamaApi/api/tags" -TimeoutSec 3
} catch {
    $serveCommand = "set CUDA_VISIBLE_DEVICES=0,1 && set OLLAMA_CONTEXT_LENGTH=4096 && set OLLAMA_KEEP_ALIVE=0 && `"$OllamaExe`" serve"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $serveCommand -WindowStyle Hidden | Out-Null
    Wait-HttpOk -Uri "$OllamaApi/api/tags" -TimeoutSec 60
}

Write-Host "[2/5] Ensuring Esther model exists..."
& $OllamaExe show $ModelName *> $null
if ($LASTEXITCODE -ne 0) {
    & $OllamaExe show $BaseModel *> $null
    if ($LASTEXITCODE -ne 0) {
        & $OllamaExe pull $BaseModel
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to pull base model: $BaseModel"
        }
    }

    if ($ModelName -ne $BaseModel) {
        if ([string]::IsNullOrWhiteSpace($Modelfile)) {
            throw "Modelfile is required when ModelName differs from BaseModel"
        }
        & $OllamaExe create $ModelName -f $Modelfile
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create model: $ModelName"
        }
    }
}

Write-Host "[3/5] Ensuring compatibility aliases exist..."
foreach ($alias in @("local-model", "gpt-4o-mini")) {
    & $OllamaExe show $alias *> $null
    if ($LASTEXITCODE -ne 0) {
        & $OllamaExe cp $ModelName $alias
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create alias: $alias"
        }
    }
}

Write-Host "[4/6] Ensuring vision model exists..."
if (-not [string]::IsNullOrWhiteSpace($VisionModel)) {
    & $OllamaExe show $VisionModel *> $null
    if ($LASTEXITCODE -ne 0) {
        & $OllamaExe pull $VisionModel
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to pull vision model: $VisionModel"
        }
    }
}

Write-Host "[5/6] Ensuring OpenAI-compat proxy is running..."
$env:OLLAMA_BASE = $OllamaApi
$env:OLLAMA_PROXY_PORT = "1234"
$env:OLLAMA_PROXY_DEFAULT_MODEL = $ModelName
$env:OLLAMA_PROXY_REASONING_EFFORT = "none"
try {
    Wait-HttpOk -Uri "$ProxyApi/__proxy/health" -TimeoutSec 3
} catch {
    Start-Process -FilePath $PythonExe -ArgumentList $ProxyScript -WorkingDirectory $ProjectDir -WindowStyle Hidden | Out-Null
    Wait-HttpOk -Uri "$ProxyApi/__proxy/health" -TimeoutSec 30
}

Write-Host "[6/6] Preloading model into GPU memory..."
$body = @{
    model = $ModelName
    prompt = ""
    keep_alive = -1
    stream = $false
} | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$OllamaApi/api/generate" -ContentType "application/json" -Body $body | Out-Null

if ((-not [string]::IsNullOrWhiteSpace($VisionModel)) -and ($VisionPreload -eq 1)) {
    $visionKeepAliveValue = $VisionKeepAlive
    $visionKeepAliveInt = 0
    if ([int]::TryParse($VisionKeepAlive, [ref]$visionKeepAliveInt)) {
        $visionKeepAliveValue = $visionKeepAliveInt
    }
    $visionBody = @{
        model = $VisionModel
        messages = @(@{ role = "user"; content = "ok" })
        keep_alive = $visionKeepAliveValue
        stream = $false
        options = @{ num_predict = 8 }
    } | ConvertTo-Json -Depth 8 -Compress
    Invoke-RestMethod -Method Post -Uri "$OllamaApi/api/chat" -ContentType "application/json" -Body $visionBody | Out-Null
}
