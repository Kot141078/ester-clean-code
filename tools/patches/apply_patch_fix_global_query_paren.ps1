param(
  [string]$Path = ".\run_ester_fixed.py"
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

function Get-TextEncodingInfo([string]$p) {
  $b = [System.IO.File]::ReadAllBytes($p)
  if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) {
    return @{ Name="utf8bom"; Encoding=(New-Object System.Text.UTF8Encoding($true)) }
  }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) {
    return @{ Name="utf16le"; Encoding=[System.Text.Encoding]::Unicode }
  }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFE -and $b[1] -eq 0xFF) {
    return @{ Name="utf16be"; Encoding=[System.Text.Encoding]::BigEndianUnicode }
  }
  return @{ Name="utf8"; Encoding=(New-Object System.Text.UTF8Encoding($false)) }
}

function New-Backup([string]$p) {
  $ts = (Get-Date).ToString("yyyyMMdd_HHmmss")
  $bak = "$p.bak_$ts"
  Copy-Item -LiteralPath $p -Destination $bak -Force
  return $bak
}

function Rollback([string]$bak, [string]$dst) {
  Copy-Item -LiteralPath $bak -Destination $dst -Force
  Write-Host "Rollback -> $bak" -ForegroundColor Yellow
}

# --- Bridges (ASCII only, safe for PS5) ---
# EXPLICIT BRIDGE: c=a+b (human + procedures) -> retrieval window (topk clamp)
# HIDDEN BRIDGE 1 (Ashby): requisite variety -> more candidates reduces brittleness
# HIDDEN BRIDGE 2 (Cover&Thomas): channel capacity -> clamp topk to control context bandwidth
# EARTH PARAGRAPH: This is like sensory gating: too few signals -> blind, too many -> overload.
# ------------------------------------------------

if (!(Test-Path -LiteralPath $Path)) {
  throw "File not found: $Path"
}

$encInfo = Get-TextEncodingInfo $Path
$enc = $encInfo.Encoding

$bak = New-Backup $Path
Write-Host "Backup created: $bak" -ForegroundColor Cyan

try {
  $text = [System.IO.File]::ReadAllText($Path, $enc)

  $nl = "`n"
  if ($text.Contains("`r`n")) { $nl = "`r`n" }

  $lines = $text -split "`r?`n", 0

  $idx = -1
  for ($i=0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match '^\s*resg\s*=\s*self\.global_coll\.query\(') {
      $idx = $i
      break
    }
  }
  if ($idx -lt 0) { throw "Could not find the global resg = self.global_coll.query(...) line" }

  $indent = ""
  if ($lines[$idx] -match '^(\s*)') { $indent = $Matches[1] }

  $fixed = $indent + 'resg = self.global_coll.query(query_texts=[q], n_results=max(3, int(topk // 2)))'
  $lines[$idx] = $fixed

  $outText = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $outText, $enc)

  Write-Host "PATCH OK: fixed missing parentheses in global vector query." -ForegroundColor Green
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback. Reason: " + $_.Exception.Message) -ForegroundColor Red
  Rollback $bak $Path
  throw
}
