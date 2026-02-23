param([string]$Base = "http://127.0.0.1:8090")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

"`n--- STATUS ---"
Invoke-RestMethod "$Base/mvp/autonomy/status" | ConvertTo-Json -Depth 20

"`n--- TICK ---"
$body = @{ reason = "smoke" } | ConvertTo-Json -Compress -Depth 10
Invoke-RestMethod -Method Post -Uri "$Base/mvp/autonomy/tick" -ContentType "application/json; charset=utf-8" -Body $body |
  ConvertTo-Json -Depth 20