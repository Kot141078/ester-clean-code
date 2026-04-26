param(
    [string]$ProjectDir = "",
    [string]$OllamaExe = "",
    [string]$ModelName = "esther-qwen3-32b"
)

$ErrorActionPreference = "SilentlyContinue"

if ([string]::IsNullOrWhiteSpace($ProjectDir)) {
    $ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if ([string]::IsNullOrWhiteSpace($OllamaExe)) {
    $OllamaExe = Join-Path $env:USERPROFILE "Tools\ollama-portable\ollama.exe"
}
$OllamaPattern = "*" + $OllamaExe + "*"

function Stop-MatchingProcesses {
    param(
        [string]$Label,
        [string]$Name,
        [string]$Pattern
    )

    $targets = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq $Name -and $_.CommandLine -like $Pattern }

    foreach ($target in $targets) {
        try {
            Stop-Process -Id $target.ProcessId -Force -ErrorAction Stop
            Write-Host ("[{0}] stopped PID {1}" -f $Label, $target.ProcessId)
        } catch {
            Write-Host ("[{0}] failed PID {1}: {2}" -f $Label, $target.ProcessId, $_.Exception.Message)
        }
    }
}

function Wait-NoMatchingProcesses {
    param(
        [string]$Name,
        [string]$Pattern,
        [int]$TimeoutSec = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $left = Get-CimInstance Win32_Process |
            Where-Object { $_.Name -eq $Name -and $_.CommandLine -like $Pattern }
        if (-not $left) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
}

Stop-MatchingProcesses -Label "ester-core" -Name "python.exe" -Pattern "*run_ester_fixed.py*"
Stop-MatchingProcesses -Label "ollama-proxy" -Name "python.exe" -Pattern "*ollama_openai_proxy.py*"

if (Test-Path -LiteralPath $OllamaExe) {
    & $OllamaExe stop $ModelName | Out-Null
    Start-Sleep -Milliseconds 500
}

Stop-MatchingProcesses -Label "ollama-portable" -Name "ollama.exe" -Pattern $OllamaPattern

Wait-NoMatchingProcesses -Name "python.exe" -Pattern "*run_ester_fixed.py*"
Wait-NoMatchingProcesses -Name "python.exe" -Pattern "*ollama_openai_proxy.py*"
Wait-NoMatchingProcesses -Name "ollama.exe" -Pattern $OllamaPattern
