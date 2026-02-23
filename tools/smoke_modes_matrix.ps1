param([string]$Base = $env:ESTER_API_BASE)
if (-not $Base) { $Base = "http://127.0.0.1:8080" }
$Base = $Base.TrimEnd('/')

$bodyTpl = @{
  message = "e2e?"
  use_rag = $true
}
$mods = @("judge","lmstudio","cloud")

"BASE = $Base"
""
"mode    code provider   answer"
"----    ---- --------   ------"

foreach ($m in $mods) {
  $body = $bodyTpl.Clone()
  $body.mode = $m
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri "$Base/ester/chat/message" `
              -Method Post -ContentType "application/json" `
              -Body ($body | ConvertTo-Json -Depth 5) -TimeoutSec 60
    $j = $resp.Content | ConvertFrom-Json
    "{0,-7} {1,4} {2,-10} {3}" -f $m,$resp.StatusCode,($j.provider),($j.answer -replace "\r?\n"," ")
  } catch {
    "{0,-7}    -1 ERR        $($_.Exception.Message)"
  }
}
