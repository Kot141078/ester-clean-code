param(
  [string]$Base = $env:OPENAI_API_BASE
)
if (-not $Base) { $Base = "http://127.0.0.1:1234/v1" }

try {
  $resp = Invoke-RestMethod -Uri ($Base.TrimEnd('/') + "/models") -Method GET
} catch {
  Write-Host "[fatal] ne udalos poluchit spisok modeley: $($_.Exception.Message)"
  exit 2
}

# Let's display the ID table; highlight obvious candidates for embeddings using heuristics
$rows = @()
foreach ($m in $resp.data) {
  $id = $m.id
  $maybeEmbed = ($id -match "(embed|gte|bge|e5|miniLM|text2vec)")
  $rows += [PSCustomObject]@{ id = $id; embedding_candidate = $maybeEmbed }
}
$rows | Sort-Object -Property id | Format-Table -AutoSize
Write-Host "`nSovet: vyberi model s embedding_candidate=True i postav ee v EMBED_MODEL."
