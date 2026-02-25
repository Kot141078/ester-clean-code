param(
  [string]$EnvPath = "D:\ester-project\.env"
)

$keys = @(
  'ESTER_HOME','ESTER_DATA_ROOT','ESTER_TMP_DIR','ESTER_LOG_DIR',
  'ESTER_CHAT_PERSIST','ESTER_CHAT_MEM_DIR','ESTER_CHAT_MEM_PRELOAD','ESTER_CHAT_MEM_MAX_LINES','ESTER_CHAT_SID_DEFAULT',
  'ESTER_RAG_ENABLE','ESTER_RAG_DOCS_DIR','ESTER_RAG_FORCE_PATH','ESTER_VECTOR_DB','ESTER_VECTOR_DIR',
  'ESTER_DEFAULT_MODE','ESTER_PROVIDERS_ENABLE','ESTER_PROVIDER_FALLBACK',
  'LMSTUDIO_BASE_URL','LMSTUDIO_MODEL',
  'OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_MODEL',
  'GEMINI_API_KEY','GEMINI_MODEL',
  'XAI_API_KEY','XAI_MODEL',
  'TELEGRAM_BOT_TOKEN','TELEGRAM_POLLING','TELEGRAM_WEBHOOK_URL',
  'ESTER_JWT_SECRET','ESTER_JWT_ALG',
  'ESTER_NET_AUTOBRIDGE','ESTER_EXPLICIT_BRIDGE'
)

$raw = if (Test-Path $EnvPath) { Get-Content $EnvPath -Raw -Encoding UTF8 } else { "" }

# 1) remove all duplicates by list keys
foreach($k in $keys){
  $raw = [regex]::Replace($raw, "^(?m)\s*$([regex]::Escape($k))\s*=.*\r?\n?", "")
}

# 2) garantirovat perevod stroki v kontse
if ($raw.Length -gt 0 -and -not $raw.TrimEnd().EndsWith("`n")){ $raw += "`r`n" }

# 3) return the existing unaffected lines as is, then add the critical one
$absVec = Join-Path $env:USERPROFILE ".ester\vstore\vectors"
$raw += "ESTER_VECTOR_DIR=$absVec`r`n"

# 4) zapisat
$raw | Set-Content -Path $EnvPath -Encoding UTF8
Write-Host "[env_sanitize] done"
