param([string]$Base = "http://127.0.0.1:8080")
Write-Host "== Providers status =="
iwr -UseBasicParsing "$Base/providers/status" | % Content | Write-Output

Write-Host "== Mint admin token =="
$tok = (irm -Method POST "$Base/auth/glue/mint" -ContentType "application/json" -Body '{"sub":"Owner","roles":["ADMIN"]}').token
$hdr = @{ Authorization = "Bearer $tok"; "Content-Type"="application/json" }
Write-Host "token ok"

Write-Host "== Select LM Studio =="
irm -Method POST "$Base/providers/select" -Headers $hdr -ContentType "application/json" -Body '{"provider":"lmstudio","base_url":"http://127.0.0.1:1234/v1","model":"gpt-4o-mini"}' | Write-Output

Write-Host "== List models (lmstudio) =="
iwr -UseBasicParsing "$Base/providers/models" | % Content | Write-Output

Write-Host "== Chat health =="
iwr -UseBasicParsing "$Base/chat/health" | % Content | Write-Output

Write-Host "== Chat message (short) =="
irm -Method POST "$Base/chat/message" -Headers $hdr -ContentType "application/json" -Body (@{ message="Privet, Ester"; mode="lmstudio"; rag=$false; temperature=0.3 } | ConvertTo-Json) | Write-Output