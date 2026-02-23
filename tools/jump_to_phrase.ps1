param(
  [string]$Base = "http://127.0.0.1:8080",
  [Parameter(Mandatory=$true)] [string]$Phrase,      # iskomaya fraza (kirillitsa ok)
  [int]$K = 50,
  [int]$WindowBefore = 200,
  [int]$WindowAfter = 400,
  [string]$PreferBasename = ""                       # naprimer: doc1.txt
)

function Get-RagStatus {
  $r = Invoke-WebRequest -UseBasicParsing -Uri "$Base/rag/status"
  return ($r.Content | ConvertFrom-Json)
}

function Search-Hits([string]$phrase, [int]$k) {
  $json  = @{ q = $phrase; k = $k; max_chars = 200 } | ConvertTo-Json -Compress
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  $r = Invoke-WebRequest -UseBasicParsing -Uri "$Base/rag/hybrid/search" -Method POST -ContentType 'application/json; charset=utf-8' -Body $bytes
  return ($r.Content | ConvertFrom-Json).hits
}

function Try-PickIdFromHits($hits, [string]$phrase, [string]$preferBasename) {
  if ($preferBasename -ne "") {
    $h = $hits | Where-Object { ($_.id | Split-Path -Leaf) -ieq $preferBasename } | Select-Object -First 1
    if ($h) { return $h.id }
  }
  $h = $hits | Where-Object { $_.snippet -match [regex]::Escape($phrase) } | Select-Object -First 1
  if ($h) { return $h.id }
  $h = $hits | Select-Object -First 1
  if ($h) { return $h.id }
  return $null
}

function Try-FindIdInJsonl([string]$docsPath, [string]$phrase) {
  if (-not (Test-Path $docsPath)) { return $null }
  foreach ($line in Get-Content $docsPath) {
    if (-not $line) { continue }
    try {
      $obj = $line | ConvertFrom-Json
    } catch { continue }
    $id = [string]$obj.id
    $txt = $null
    if ($obj.text -is [string]) {
      $txt = [string]$obj.text
    } else {
      # uproschennyy poisk: serializuem vlozhennuyu strukturu v stroku i proverim vkhozhdenie
      $txt = ($obj.text | ConvertTo-Json -Depth 8 -Compress)
    }
    if ($txt -and ($txt -match [regex]::Escape($phrase))) {
      return $id
    }
  }
  return $null
}

function Jump-Window([string]$id, [string]$phrase, [int]$wb, [int]$wa) {
  $idEsc = [uri]::EscapeDataString($id)
  $qEsc  = [uri]::EscapeDataString($phrase)
  $url = "$Base/rag/hybrid/doc?id=$idEsc&q=$qEsc&window_before=$wb&window_after=$wa&include_meta=1"
  return Invoke-WebRequest -UseBasicParsing -Uri $url
}

# --- main ---
Write-Host "Base: $Base"
Write-Host "Phrase: $Phrase"
$st = Get-RagStatus
$docsPath = [string]$st.docs_path

$hits = Search-Hits -phrase $Phrase -k $K
$id = Try-PickIdFromHits -hits $hits -phrase $Phrase -preferBasename $PreferBasename

if (-not $id) {
  Write-Warning "ID not found in search hits; fallback to local JSONL"
  $id = Try-FindIdInJsonl -docsPath $docsPath -phrase $Phrase
}

if (-not $id) { throw "Unable to resolve id for phrase '$Phrase'" }

Write-Host "ID: $id"
$r = Jump-Window -id $id -phrase $Phrase -wb $WindowBefore -wa $WindowAfter
$r.Content
