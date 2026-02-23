Param(
  [string]$Sub = $env:ESTER_OWNER_SUB,
  [string[]]$Roles = @("owner","admin"),
  [int]$Ttl = 30,
  [switch]$Clipboard = $true,
  [string]$Save = "data\owner_jwt.token"
)
if ($env:JWT_TTL_DAYS) { try { $Ttl = [int]$env:JWT_TTL_DAYS } catch {} }
function Invoke-Py {
  param([string[]]$Args)
  $pyCmd = Get-Command py -ErrorAction SilentlyContinue
  if ($pyCmd) { & $pyCmd.Path @Args; return $LASTEXITCODE }
  $py2 = Get-Command python -ErrorAction SilentlyContinue
  if ($py2) { & $py2.Path @Args; return $LASTEXITCODE }
  throw "Python not found (py/python)"
}
$args = @("scripts/gen_owner_jwt.py","--sub",$Sub,"--save",$Save,"--ttl",$Ttl,"--print-only")
if ($Roles -and $Roles.Count -gt 0) { $args += @("--roles"); $args += $Roles }
$null = Invoke-Py $args
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to generate token"; exit 1 }
try { $tok = Get-Content -Path $Save -TotalCount 1 -ErrorAction Stop } catch { Write-Error "Token file not found: $Save"; exit 1 }
if ($Clipboard) { $tok | Set-Clipboard }
"OK owner JWT saved to $Save"
"Token (first 32): $($tok.Substring(0, [Math]::Min(32, $tok.Length)))..."
