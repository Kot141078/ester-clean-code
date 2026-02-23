Param(
  [string]$EnvPath = ".env"
)
$OUT_DIR = "config"
$OUT_CLEAN = Join-Path $OUT_DIR ".env.cleaned"
$OUT_BAD   = Join-Path $OUT_DIR ".env.invalid"

function Strip-InlineComment([string]$val) {
  $out = New-Object System.Text.StringBuilder
  $q = $null
  for ($i=0; $i -lt $val.Length; $i++) {
    $ch = $val[$i]
    if ($ch -eq '"' -or $ch -eq "'") {
      if ($q -eq $ch) { $q = $null } elseif ($q -eq $null) { $q = $ch }
    }
    if ($ch -eq '#' -and $q -eq $null) { break }
    $out.Append($ch) | Out-Null
  }
  return $out.ToString().TrimEnd()
}
function Normalize-Value([string]$v) {
  $v = $v.Trim()
  if ($v.Length -ge 2) {
    $first = $v.Substring(0,1)
    $last  = $v.Substring($v.Length-1,1)
    if ($first -eq $last -and ($first -eq '"' -or $first -eq "'")) { $v = $v.Substring(1, $v.Length-2) }
  }
  return $v
}

$clean = New-Object System.Collections.Generic.List[string]
$bad   = New-Object System.Collections.Generic.List[string]

if (-not (Test-Path $EnvPath)) {
  Write-Output (@{ ok=$false; error=".env not found"; path=$EnvPath } | ConvertTo-Json -Compress)
  exit 1
}
New-Item -ItemType Directory -Force -Path $OUT_DIR | Out-Null
$lines = Get-Content -Path $EnvPath -Encoding UTF8 -ErrorAction SilentlyContinue
$reKey = '^[A-Za-z_][A-Za-z0-9_]*$'

for ($i=0; $i -lt $lines.Count; $i++) {
  $raw = $lines[$i].TrimEnd("`r","`n")
  $lineno = $i + 1
  if ([string]::IsNullOrWhiteSpace($raw) -or $raw.TrimStart().StartsWith("#")) {
    $clean.Add($raw) | Out-Null
    continue
  }
  if ($raw -notmatch "=") {
    $bad.Add("$($lineno):$raw") | Out-Null
    continue
  }
  $parts = $raw.Split("=",2)
  $key = $parts[0].Trim()
  $val = $parts[1]
  if ($key -notmatch $reKey) {
    $bad.Add("$($lineno):$raw") | Out-Null
    continue
  }
  $val = Strip-InlineComment $val
  $val = Normalize-Value $val
  $clean.Add("$key=$val") | Out-Null
}

$clean -join "`n" | Set-Content -Path $OUT_CLEAN -Encoding UTF8
$bad   -join "`n" | Set-Content -Path $OUT_BAD   -Encoding UTF8
@{ ok=$true; clean=$OUT_CLEAN; invalid=$OUT_BAD; invalid_count=$bad.Count } | ConvertTo-Json -Compress
