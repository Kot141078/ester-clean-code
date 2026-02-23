param(
  [string]$Base = "http://127.0.0.1:8080"
)
# UTF-8 JSON body sender (WinPS 5.1-safe)
function Send-JsonUtf8([string]$Uri, [hashtable]$Body) {
  $json  = ($Body | ConvertTo-Json -Compress)
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method POST -ContentType 'application/json; charset=utf-8' -Body $bytes
}

Write-Host "== /rag/status =="
try { iwr -UseBasicParsing "$Base/rag/status" } catch { $_ }

Write-Host "== search 'Ester' =="
try { Send-JsonUtf8 "$Base/rag/hybrid/search" @{ q = "Ester"; k = 5 } } catch { $_ }