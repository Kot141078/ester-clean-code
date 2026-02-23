Param(
  [string]$EnvPath = (Join-Path (Get-Location) '.env')
)
function Invoke-Py {
  param([string[]]$Args)
  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) { & $pyCmd.Path @Args; return $LASTEXITCODE }
  $py2 = Get-Command python -ErrorAction SilentlyContinue
  if ($py2) { & $py2.Path @Args; return $LASTEXITCODE }
  throw "Python not found (py/python)"
}
$null = Invoke-Py @("scripts/env_sanitize.py", $EnvPath)
