# С0/skripts/kisk_admin_token.ps1 - generate admin-ZhVT and check /admin (Invoke-WebRequest)
# Bridges: (Explicit) Enderton - check predicates; (Hidden) Ashby is a simple regulator; Janes - the likelihood of a valid session.
# Earthly paragraph: a quick knock on Windows without UI. Dependencies: Pothon, PowerShell.
# c=a+b

param(
  [string]$BaseUrl = "http://127.0.0.1:8080",
  [string]$UserName = "Owner",
  [string]$Role = "admin",
  [int]$Ttl = 600
)

if (-not $env:JWT_SECRET) {
  Write-Warning "[quick_admin_token] JWT_SECRET ne zadan, ispolzuem 'devsecret' (NE dlya proda)."
  $env:JWT_SECRET = "devsecret"
}

$token = python tools/jwt_mint.py --user $UserName --role $Role --ttl $Ttl
Write-Host "[quick_admin_token] JWT: " ($token.Substring(0, [Math]::Min(24, $token.Length)) + "…")

try {
  $resp = Invoke-WebRequest -Uri "$BaseUrl/admin" -Headers @{ Authorization = "Bearer $token" } -Method GET -MaximumRedirection 0 -ErrorAction Stop
  $code = $resp.StatusCode.value__
} catch {
  if ($_.Exception.Response) {
    $code = $_.Exception.Response.StatusCode.value__
  } else {
    $code = -1
  }
}
Write-Host "[quick_admin_token] /admin => HTTP $code"
if ($code -ge 200 -and $code -lt 400) {
  Write-Host "[quick_admin_token] OK"
} else {
  Write-Warning "[quick_admin_token] /admin vernul $code — prover RBAC/JWT_SECRET/prilozhenie."
}
