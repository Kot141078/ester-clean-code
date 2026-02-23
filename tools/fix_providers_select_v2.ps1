New-Item -ItemType Directory -Force -Path .\tools | Out-Null
@'
param(
  [ValidateSet("A","B")] [string]$Mode = "A",
  [string]$ApiHost,
  [string]$ApiPort,
  [switch]$AllowFileFallback = $true
)

if (-not $ApiHost -or $ApiHost.Trim() -eq "") { $ApiHost = $env:ESTER_HOST }
if (-not $ApiHost -or $ApiHost.Trim() -eq "") { $ApiHost = "127.0.0.1" }
if (-not $ApiPort -or $ApiPort.Trim() -eq "") { $ApiPort = $env:ESTER_PORT }
if (-not $ApiPort -or $ApiPort.Trim() -eq "") { $ApiPort = "8137" }

# KLYuChEVOE: bez $Var: srazu posle peremennoy
$BASE = "http://{0}:{1}" -f $ApiHost, $ApiPort

Write-Host "[fix-providers-select v3] BASE = $BASE"
Write-Host "[fix-providers-select v3] Mode = $Mode (A=prosmotr, B=vypolnit)"

function Do-PostJson {
  param([string]$Url, [hashtable]$Body, [hashtable]$Headers)
  $json = ($Body | ConvertTo-Json -Compress -Depth 6)
  if ($Mode -eq "A") { Write-Host "POST $Url"; Write-Host $json; return $null }
  try { Invoke-RestMethod -Method POST -Uri $Url -ContentType "application/json" -Headers $Headers -Body $json }
  catch { Write-Warning ("POST {0} -> {1}" -f $Url, $_.Exception.Message); $null }
}

function Do-Get {
  param([string]$Url)
  if ($Mode -eq "A") { Write-Host "GET $Url"; return $null }
  try { Invoke-WebRequest -UseBasicParsing -Uri $Url }
  catch { Write-Warning ("GET {0} -> {1}" -f $Url, $_.Exception.Message); $null }
}

Write-Host ("ENV ESTER_HOST={0} ESTER_PORT={1} ESTER_DATA_ROOT={2}" -f $env:ESTER_HOST, $env:ESTER_PORT, $env:ESTER_DATA_ROOT)

# 1) Mint admin token
$mintBody = @{ sub = "Owner"; roles = @("ADMIN") }
$mint = Do-PostJson -Url "$BASE/auth/glue/mint" -Body $mintBody -Headers @{}
$tok = if ($mint) { $mint.token } else { "<preview-mode>" }
$hdr = @{ Authorization = "Bearer $tok"; "Content-Type" = "application/json" }

# 2) Doregistrirovat blyuprint
$modsBody = @{ modules = @("routes.providers_select_patch") }
$discover = Do-PostJson -Url "$BASE/app/discover/register" -Body $modsBody -Headers @{}

# 3) Vybrat provaydera
$selBody = @{ provider = "openai" }
$select = Do-PostJson -Url "$BASE/providers/select" -Body $selBody -Headers $hdr

# 4) Proverka statusa
$statusRaw = Do-Get -Url "$BASE/providers/status"
if ($statusRaw) {
  try {
    $st = $statusRaw.Content | ConvertFrom-Json
    Write-Host ("`n[status] active_provider: {0}, lmstudio_probe: {1}, authoring_backend: {2}" -f $st.active_provider, $st.lmstudio_probe, $st.authoring_backend)
  } catch { Write-Host "[status] raw:"; Write-Host $statusRaw.Content }
}

# 5) Proverka registratsii marshruta
$scan = Do-Get -Url "$BASE/app/discover/scan"
$hasRoute = $false
if ($scan) {
  try {
    $j = $scan.Content | ConvertFrom-Json
    foreach ($r in $j.routes.items) {
      if ($r.path -eq "/providers/select" -and $r.methods -contains "POST") { $hasRoute = $true; break }
    }
    Write-Host ("[verify] /providers/select registered: {0}" -f $hasRoute)
  } catch { Write-Host "[verify] raw:"; Write-Host $scan.Content }
}

# 6) Fayl-folbek, esli discover/select ne proshli (Mode B)
if ($Mode -eq "B" -and -not $hasRoute -and $AllowFileFallback) {
  $dr = if ($env:ESTER_DATA_ROOT) { $env:ESTER_DATA_ROOT } elseif ($env:ESTER_DATA_DIR) { $env:ESTER_DATA_DIR } else { Join-Path (Get-Location) "data" }
  $path = Join-Path $dr "app\providers\active.json"
  $dir  = Split-Path $path -Parent
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  @{ active = "openai" } | ConvertTo-Json | Set-Content -Path $path -Encoding UTF8
  Write-Warning ("[fallback] wrote {0}" -f $path)
  $statusRaw2 = Do-Get -Url "$BASE/providers/status"
  if ($statusRaw2) {
    try { $st2 = $statusRaw2.Content | ConvertFrom-Json; Write-Host ("[status after fallback] active_provider: {0}" -f $st2.active_provider) }
    catch { Write-Host $statusRaw2.Content }
  }
}

Write-Host "`n[fix-providers-select v3] Done."
'@ | Set-Content -Path .\tools\fix_providers_select.ps1 -Encoding UTF8
