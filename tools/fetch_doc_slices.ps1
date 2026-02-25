param(
  [Parameter(Mandatory=$true)] [string]$Base,      # naprimer http://127.0.0.1:8080
  [Parameter(Mandatory=$true)] [string]$Id,        # id iz /rag/hybrid/search
  [string]$OutFile = ".\doc.txt",
  [int]$Start = 0,
  [int]$MaxChars = 2000,        # server vse ravno ogranichit po DOC_MAX_CHARS_PER_SLICE
  [int]$MaxTotal = 200000,      # insurance: maximum symbols that we can collect
  [switch]$IncludeMeta
)

function Get-DocSlice {
  param(
    [string]$Id,
    [int]$Start,
    [int]$MaxChars,
    [bool]$WithMeta
  )
  $idEsc = [uri]::EscapeDataString($Id)
  $url = "$Base/rag/hybrid/doc?id=$idEsc&start=$Start&max_chars=$MaxChars"
  if ($WithMeta) { $url += "&include_meta=1" }
  return Invoke-WebRequest -UseBasicParsing -Uri $url
}

Write-Host "Fetch slices from $Base"
Write-Host "ID: $Id"
Write-Host "Output: $OutFile"

if (Test-Path $OutFile) { Remove-Item $OutFile -Force }

$downloaded = 0
$cursor = $Start
$metaPrinted = $false

while ($downloaded -lt $MaxTotal) {
  $resp = Get-DocSlice -Id $Id -Start $cursor -MaxChars $MaxChars -WithMeta:([bool]$IncludeMeta)
  $obj = $resp.Content | ConvertFrom-Json
  if (-not $obj.ok) { throw ("Server error: " + ($obj | ConvertTo-Json -Compress)) }

  if ($IncludeMeta -and -not $metaPrinted -and ($obj.PSObject.Properties.Name -contains 'meta')) {
    "# META:" | Out-File -FilePath $OutFile -Append -Encoding utf8
    ($obj.meta | ConvertTo-Json -Depth 6) | Out-File -FilePath $OutFile -Append -Encoding utf8
    "`n# TEXT:" | Out-File -FilePath $OutFile -Append -Encoding utf8
    $metaPrinted = $true
  }

  $text = [string]$obj.text
  $text | Out-File -FilePath $OutFile -Append -Encoding utf8

  $got = $text.Length
  $downloaded += $got
  $cursor = $obj.start + $obj.max_chars

  Write-Host ("slice: start={0} len={1} has_more={2} total={3}" -f $obj.start, $got, $obj.has_more, $downloaded)

  if (-not $obj.has_more) { break }
  if ($downloaded -ge $MaxTotal) { Write-Warning "Reached MaxTotal=$MaxTotal"; break }
}

Write-Host ("Done. Saved {0} chars to {1}" -f $downloaded, $OutFile)
