param([string]$Base = "http://127.0.0.1:8090")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$def = Invoke-RestMethod "$Base/mvp/agents/manifest/default"
$body = @{ yaml = $def.yaml; strict = $false } | ConvertTo-Json -Compress -Depth 20

Invoke-RestMethod -Method Post -Uri "$Base/mvp/agents/manifest/preview" `
  -ContentType "application/json; charset=utf-8" -Body $body | ConvertTo-Json -Depth 20