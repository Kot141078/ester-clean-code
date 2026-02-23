[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Uri,
  [ValidateSet('POST','PUT','PATCH')][string]$Method='POST',
  # Pri zapuske cherez -File argumenty prikhodyat strokami.
  # Razreshaem I stroku (gotovyy JSON), I khesh-tablitsu.
  [Parameter(Mandatory=$true)][object]$Body
)
$ErrorActionPreference='Stop'

function Convert-ToUtf8Bytes([string]$s) {
  [System.Text.Encoding]::UTF8.GetBytes($s)
}

if ($Body -is [string]) {
  # Esli eto JSON-stroka
  $json = $Body
} elseif ($Body -is [hashtable] -or $Body -is [System.Collections.IDictionary]) {
  $json = ($Body | ConvertTo-Json -Depth 10 -Compress)
} else {
  # Poprobuem na vsyakiy sluchay serializovat kak obekt
  $json = ($Body | ConvertTo-Json -Depth 10 -Compress)
}

$bytes = Convert-ToUtf8Bytes $json
Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method $Method `
  -ContentType 'application/json; charset=utf-8' -Body $bytes
