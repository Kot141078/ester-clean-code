[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$Uri,
  [ValidateSet('POST','PUT','PATCH')][string]$Method='POST',
  # When run via -File, the arguments come in strings.
  # We resolve both the string (ready JSION) and the hash table.
  [Parameter(Mandatory=$true)][object]$Body
)
$ErrorActionPreference='Stop'

function Convert-ToUtf8Bytes([string]$s) {
  [System.Text.Encoding]::UTF8.GetBytes($s)
}

if ($Body -is [string]) {
  # If this is a JSION string
  $json = $Body
} elseif ($Body -is [hashtable] -or $Body -is [System.Collections.IDictionary]) {
  $json = ($Body | ConvertTo-Json -Depth 10 -Compress)
} else {
  # Let's try to serialize as an object just in case
  $json = ($Body | ConvertTo-Json -Depth 10 -Compress)
}

$bytes = Convert-ToUtf8Bytes $json
Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method $Method `
  -ContentType 'application/json; charset=utf-8' -Body $bytes
