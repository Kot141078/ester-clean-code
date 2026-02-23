param([string]$Base = "http://127.0.0.1:8090")
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ensure manifest applied
& "$PSScriptRoot\smoke_manifest_apply_memory.ps1" -Base $Base | Out-Null

$tasks = @(
  "U menya oshibki i vse tormozit, prover health/metrics",
  "Naydi po baze dokument pro RBAC i protsitiruy",
  "Mne nuzhen novyy agent: YAML + geyty, sdelay chernovik",
  "Prosto pomogi vybrat ispolnitelya"
)

foreach($t in $tasks){
  "`nTASK: $t"
  $body = @{ task = $t } | ConvertTo-Json -Compress -Depth 10
  Invoke-RestMethod -Method Post -Uri "$Base/synergy/assign/advice" -ContentType "application/json; charset=utf-8" -Body $body |
    ConvertTo-Json -Depth 20
}