param([string]$Base = "http://127.0.0.1:8090")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ensure manifest applied
& "$PSScriptRoot\smoke_manifest_apply_memory.ps1" -Base $Base | Out-Null

$agents = @(
  "est.dispatcher.synergy_mvp.v1",
  "est.ops.health_mvp.v1",
  "est.librarian.knowledge_mvp.v1",
  "est.builder.suite_mvp.v1"
)

foreach($a in $agents){
  "`n== $a =="
  $payload = @{ agent = $a; text = "SMOKE: sdelay korotkiy otvet po roli agenta"; dry_run = $true } | ConvertTo-Json -Compress -Depth 20
  Invoke-RestMethod -Method Post -Uri "$Base/mvp/agents/suite/run" -ContentType "application/json; charset=utf-8" -Body $payload |
    ConvertTo-Json -Depth 20
}