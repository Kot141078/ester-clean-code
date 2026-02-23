param(
  [string]$Base = "http://127.0.0.1:8080"
)
function Send-JsonUtf8([string]$Uri, [hashtable]$Body) {
  $json  = ($Body | ConvertTo-Json -Compress)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method POST -ContentType 'application/json; charset=utf-8' -Body $bytes
}

Write-Host "== status =="
iwr -UseBasicParsing "$Base/rag/status"

Write-Host "== hits with snippet (max_chars=300) =="
Send-JsonUtf8 "$Base/rag/hybrid/search" @{ q = "Ester"; k = 3; max_chars = 300 }

Write-Host "== hits with FULL text (include_text=true) =="
Send-JsonUtf8 "$Base/rag/hybrid/search" @{ q = "Ester"; k = 1; include_text = $true; max_chars = 0 }
