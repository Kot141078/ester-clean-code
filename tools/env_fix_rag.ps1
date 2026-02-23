# tools/env_fix_rag.ps1
# -*- powershell -*-
param(
  [string]$Model = "text-embedding-nomic-embed-text-v1.5",
  [int]$Dim = 768,
  [switch]$WriteLocalEnv  # pri ukazanii sozdast/obnovit .env.local
)

function Die($msg){ Write-Error $msg; exit 1 }

# 1) Baza LM Studio po OpenAI-sovmestimomu API
if (-not $env:OPENAI_API_BASE) { $env:OPENAI_API_BASE = "http://127.0.0.1:1234/v1" }
if (-not $env:OPENAI_API_KEY)  { $env:OPENAI_API_KEY  = "lm-studio" }

# 2) Kanonicheskoe imya i alias
$env:EMBED_MODEL        = $Model
$env:EMBEDDINGS_MODEL   = $Model
$env:EMBEDDINGS_API_BASE = $env:OPENAI_API_BASE
$env:EMBEDDINGS_API_KEY  = $env:OPENAI_API_KEY

# 3) Put dannykh (esli kto-to sbrosil v D:\)
if (-not $env:ESTER_DATA_ROOT -or $env:ESTER_DATA_ROOT -eq "D:\") {
  $env:ESTER_DATA_ROOT = (Resolve-Path ".\data").Path
}

# 4) LM Studio vklyuchen
$env:LMSTUDIO_ENABLE   = "1"
$env:LMSTUDIO_URL      = $env:OPENAI_API_BASE
$env:PRIMARY_PROVIDER  = "lmstudio"
$env:DEFAULT_CHAT_PROVIDER = "lmstudio"

# 5) Bystraya validatsiya embeddingov
$ping = powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\embed_ping.ps1 2>&1
if ($LASTEXITCODE -ne 0 -or ($ping -join "`n") -notmatch "ok|dim") {
  Die "[fatal] embeddings endpoint ne otvechaet. Prover, chto model `"$Model`" zagruzhena v LM Studio i otkryt /v1/embeddings"
}

# 6) Proverka razmernosti (iz stroki pinga)
if (($ping -join "`n") -match "dim=(\d+)") {
  $got = [int]$Matches[1]
  if ($got -ne $Dim) {
    Write-Warning "Ozhidalas razmernost $Dim, u endpointa $got. Ubedis, chto vybrana vernaya model."
  }
}

# 7) Optsionalno — .env.local
if ($WriteLocalEnv) {
  $out = @()
  $out += "OPENAI_API_BASE=$($env:OPENAI_API_BASE)"
  $out += "OPENAI_API_KEY=$($env:OPENAI_API_KEY)"
  $out += "EMBED_MODEL=$($env:EMBED_MODEL)"
  $out += "EMBEDDINGS_MODEL=$($env:EMBEDDINGS_MODEL)"
  $out += "LMSTUDIO_ENABLE=1"
  $out += "ESTER_DATA_ROOT=$($env:ESTER_DATA_ROOT)"
  $out += "PRIMARY_PROVIDER=lmstudio"
  $out += "DEFAULT_CHAT_PROVIDER=lmstudio"
  Set-Content -Path ".\.env.local" -Value ($out -join "`n") -Encoding UTF8
  Write-Host "OK: .env.local zapisan"
}

Write-Host "OK: okruzhenie dlya RAG vyrovneno. EMBED_MODEL=$($env:EMBED_MODEL); DATA_ROOT=$($env:ESTER_DATA_ROOT)"
