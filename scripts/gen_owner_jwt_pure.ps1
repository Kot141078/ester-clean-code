Param(
  [string]$Sub = $(if ($env:ESTER_OWNER_SUB) { $env:ESTER_OWNER_SUB } else { "owner" }),
  [string[]]$Roles = @("owner","admin"),
  [int]$TtlDays = $(if ($env:JWT_TTL_DAYS) { [int]$env:JWT_TTL_DAYS } else { 30 }),
  [string]$Iss = $(if ($env:JWT_ISS) { $env:JWT_ISS } else { "ester" }),
  [string]$Aud = $(if ($env:JWT_AUD) { $env:JWT_AUD } else { "ester-ui" }),
  [string]$Alg = $(if ($env:JWT_ALG) { $env:JWT_ALG } else { "HS256" }),
  [string]$Secret = $(if ($env:JWT_SECRET) { $env:JWT_SECRET } else { "change-me-please-32-bytes" }),
  [string]$Save = "data\owner_jwt.token",
  [switch]$Clipboard = $true
)
if ($Alg -ne "HS256") { throw "Only HS256 supported in pure PS" }

function B64Url([byte[]]$bytes) {
  $b = [Convert]::ToBase64String($bytes)
  $b = $b.TrimEnd('=') -replace '\+','-' -replace '/','_'
  return $b
}

$enc = [System.Text.Encoding]::UTF8
$now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$exp = ([DateTimeOffset]::UtcNow.AddDays($TtlDays)).ToUnixTimeSeconds()

$payloadObj = [ordered]@{
  sub   = $Sub
  iss   = $Iss
  aud   = $Aud
  iat   = [int64]$now
  nbf   = [int64]$now
  exp   = [int64]$exp
  jti   = [guid]::NewGuid().ToString()
  roles = $Roles
  scope = "owner:all"
}
$headerObj = [ordered]@{ typ="JWT"; alg=$Alg }

$h = B64Url($enc.GetBytes(($headerObj | ConvertTo-Json -Depth 5 -Compress)))
$p = B64Url($enc.GetBytes(($payloadObj | ConvertTo-Json -Depth 5 -Compress)))
$signing = $enc.GetBytes("$h.$p")

# VAZhNO: pravilnyy vyzov konstruktora s byte[] v PS5
$hmac = [System.Security.Cryptography.HMACSHA256]::new([byte[]]($enc.GetBytes($Secret)))
$sig = B64Url($hmac.ComputeHash($signing))
$token = "$h.$p.$sig"

New-Item -ItemType Directory -Force -Path (Split-Path $Save) | Out-Null
$token | Set-Content -Path $Save -Encoding UTF8
if ($Clipboard) { $token | Set-Clipboard }

@{
  ok = $true
  token_saved = $Save
  token_preview = $token.Substring(0, [Math]::Min(32, $token.Length)) + "..."
  exp = $exp
} | ConvertTo-Json -Depth 5
