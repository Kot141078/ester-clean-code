param(
  [string]$Base = "http://127.0.0.1:8090",
  [string]$AgentId = "director"
)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# tvoe tekuschee API: { id, payload }
$body = @{
  id = $AgentId
  payload = @{ text = "Sostav plan na den (smoke)" }
} | ConvertTo-Json -Compress -Depth 10

Invoke-RestMethod -Method Post -Uri "$Base/mvp/agents/run" -ContentType "application/json; charset=utf-8" -Body $body |
  ConvertTo-Json -Depth 20