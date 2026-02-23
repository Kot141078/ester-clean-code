param([string]$Base="http://127.0.0.1:8080")
Write-Host "== Health =="
iwr -UseBasicParsing "$Base/chat/health" | % Content | Write-Output

Write-Host "== Simple message (lmstudio) =="
$resp = irm -Method POST "$Base/chat/message" -ContentType "application/json" -Body (@{
  message="Ester, kakie moduli ty vidish?";
  mode="lmstudio";
  rag=$true;
  temperature=0.2
} | ConvertTo-Json)
$resp | ConvertTo-Json -Depth 6 | Write-Output
