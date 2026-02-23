param([string]$Base = "http://127.0.0.1:8090")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$body = @{
  sid="smoke"
  mode="judge"
  use_rag=$true
  message="Privet! Skazhi 2+2."
  temperature=0.2
} | ConvertTo-Json -Compress -Depth 10

Invoke-RestMethod -Method Post -Uri "$Base/ester/chat/message" -ContentType "application/json; charset=utf-8" -Body $body |
  ConvertTo-Json -Depth 20