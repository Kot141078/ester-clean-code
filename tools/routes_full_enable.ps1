# tools\routes_full_enable.ps1
# Purpuse: enable extended routes so that the RAG/memory is hooked up to the portal.
# Bezopasno: delaet bekap starogo extra_routes.json i pishet novyy.

Param(
  [string]$DataRoot = $env:ESTER_DATA_ROOT
)

# --- helpers (ASSII-only messages so that there is no krakozyabr) ---
function Info($m){ Write-Host "[info] $m" }
function Ok($m){ Write-Host "[ok]   $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[warn] $m" -ForegroundColor Yellow }
function Die($m){ throw $m }

# 1) Resolve data root
if ([string]::IsNullOrWhiteSpace($DataRoot)) {
  $DataRoot = Join-Path (Get-Location) "data"
  Info "ESTER_DATA_ROOT not set, fallback -> $DataRoot"
}
$AppDir = Join-Path $DataRoot "app"
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
$Extra = Join-Path $AppDir "extra_routes.json"

# 2) Bekap
if (Test-Path $Extra) {
  Copy-Item $Extra "$Extra.bak" -Force
  Info "backup -> $Extra.bak"
}

# 3) Spisok moduley marshrutov.
# Zamet: daem ODNIM spiskom i varianty s prefiksom "ester." i bez.
# The extra ones will simply be skipped by your bootloader, this is normal.
$routes = @(
  # bazovye stranitsy/portal/doki
  "routes.root_routes",
  "routes.docs_routes",
  "routes.register_ui",
  "routes.portal_routes",

  # provaydery/gipotezy/bekap/operatsii
  "routes.providers_routes",
  "routes.hypotheses_routes",
  "routes.ops_backup_routes",

  # pamyat/RAG/ingest
  "routes.mem_routes",
  "routes.mem_kg_routes",
  "routes.rag_routes",
  "routes.ingest_routes",

  # bezopasnost/sluzhebnye
  "routes.security_middleware",
  "routes.routes_rules",

  # te zhe varianty pod prostranstvom ester.*
  "ester.routes.root_routes",
  "ester.routes.docs_routes",
  "ester.routes.register_ui",
  "ester.routes.portal_routes",

  "ester.routes.providers_routes",
  "ester.routes.hypotheses_routes",
  "ester.routes.ops_backup_routes",

  "ester.routes.mem_routes",
  "ester.routes.mem_kg_routes",
  "ester.routes.rag_routes",
  "ester.routes.ingest_routes",

  "ester.routes.security_middleware",
  "ester.routes.routes_rules"
) | Select-Object -Unique

# 4) Write JSION (ASSII) so that PowerShell does not spoil the quotes
$Json = ($routes | ConvertTo-Json -Depth 3)
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($Extra, $Json, $Utf8NoBom)

Ok "routes written -> $Extra"
Info "count = $($routes.Count)"
