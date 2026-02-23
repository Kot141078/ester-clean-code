param(
  [string]$Base = $env:OPENAI_API_BASE,
  [string]$Key  = $env:OPENAI_API_KEY,
  [string]$Model = $env:EMBED_MODEL
)

if (-not $Base)  { $Base  = "http://127.0.0.1:1234/v1" }
if (-not $Key)   { $Key   = "lm-studio" }
if (-not $Model) { Write-Host "[fatal] EMBED_MODEL ne zadan"; exit 2 }

$BodyObj = @{ model = $Model; input = "ping" }
$Body = $BodyObj | ConvertTo-Json -Depth 5

try {
  $resp = Invoke-RestMethod -Uri ($Base.TrimEnd('/') + "/embeddings") `
                            -Headers @{ Authorization = "Bearer $Key" } `
                            -Method POST `
                            -ContentType "application/json" `
                            -Body $Body
} catch {
  Write-Host "[fatal] zapros ne udalsya: $($_.Exception.Message)"
  Write-Host "Podskazka: v EMBED_MODEL dolzhen byt **embedding**-model (naprimer nomic-embed-text, bge-m3, gte-small)."
  exit 3
}

$dim = $resp.data[0].embedding.Count
Write-Host "[ok] embeddings online; dim=$dim; model=$Model"
