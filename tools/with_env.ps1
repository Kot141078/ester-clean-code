# <repo-root>\tools\with_env.ps1
# Loads KEY=VALUE from .env into *current process* env, then runs the given command.
# Usage:
#   .\tools\with_env.ps1 .\.env .\.venv\Scripts\python.exe .\tools\diag_openai_wire.py
#   .\tools\with_env.ps1 .\.venv\Scripts\python.exe .\app.py

param(
  [Parameter(Position=0)]
  [string]$EnvPath,

  [Parameter(Position=1)]
  [string]$Exe,

  [Parameter(Position=2, ValueFromRemainingArguments=$true)]
  [string[]]$ExeArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-ProjectEnvPath {
  # tools\with_env.ps1 -> project root is one level up
  $default = Join-Path $PSScriptRoot "..\.env"
  return (Resolve-Path -LiteralPath $default).Path
}

# If user called: with_env.ps1 <exe> <args...>
# then EnvPath is actually exe, Exe is actually first arg, etc.
$defaultEnv = Resolve-ProjectEnvPath

if ($EnvPath -and -not $Exe) {
  throw "Usage: with_env.ps1 [path_to_env] <exe> [args...]"
}

if ($EnvPath -and $Exe) {
  $envExt = [System.IO.Path]::GetExtension($EnvPath).ToLowerInvariant()
  $looksLikeEnv = ($envExt -eq ".env") -or ([System.IO.Path]::GetFileName($EnvPath).ToLowerInvariant() -eq ".env")

  # If first argument is not an .env file, treat it as exe and shift args
  if (-not $looksLikeEnv) {
    $ExeArgs = @($Exe) + @($ExeArgs)
    $Exe = $EnvPath
    $EnvPath = $defaultEnv
  }
} else {
  # EnvPath omitted entirely
  $EnvPath = $defaultEnv
}

if (-not (Test-Path -LiteralPath $EnvPath)) {
  throw "Env file not found: $EnvPath"
}

# Load .env
Get-Content -LiteralPath $EnvPath -Encoding UTF8 | ForEach-Object {
  $line = $_.Trim()
  if (-not $line) { return }
  if ($line.StartsWith("#")) { return }

  # allow: export KEY=VALUE
  if ($line.StartsWith("export ")) { $line = $line.Substring(7).Trim() }

  $parts = $line.Split("=", 2)
  if ($parts.Count -ne 2) { return }

  $k = $parts[0].Trim()
  $v = $parts[1].Trim()

  # Strip matching outer quotes
  if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
    if ($v.Length -ge 2) { $v = $v.Substring(1, $v.Length-2) }
  }

  if ($k) {
    [Environment]::SetEnvironmentVariable($k, $v, "Process")
  }
}

# Run command
if (-not $Exe) { throw "No executable provided." }

& $Exe @ExeArgs
exit $LASTEXITCODE
