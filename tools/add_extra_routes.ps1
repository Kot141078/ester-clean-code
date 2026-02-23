
function Invoke-Py {
  param([string[]]$Args)
  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) { & $pyCmd.Path @Args; return $LASTEXITCODE }
  $py2 = Get-Command python -ErrorAction SilentlyContinue
  if ($py2) { & $py2.Path @Args; return $LASTEXITCODE }
  throw "Python not found (py/python)"
}

Invoke-Py @("tools/add_extra_routes.py")
