param(
  [string]$Path = ".\run_ester_fixed.py",
  [switch]$Rollback,
  [string]$FromBackup = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

# ============================================================
# EXPLICIT BRIDGE: c=a+b -> empathy uses same memory substrate as main vector memory (one client)
# HIDDEN BRIDGE 1 (Ashby): reduce unintended variety (two clients) to stabilize behavior
# HIDDEN BRIDGE 2 (Cover&Thomas): remove duplicate channel/state; single path = less entropy
# EARTH: two steering wheels on one car is not redundancy, it's a crash generator
# ============================================================

function Get-FileEncoding([string]$p) {
  $b = [System.IO.File]::ReadAllBytes($p)
  if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) {
    return (New-Object System.Text.UTF8Encoding($true))  # UTF-8 BOM
  }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) { return [System.Text.Encoding]::Unicode }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFE -and $b[1] -eq 0xFF) { return [System.Text.Encoding]::BigEndianUnicode }
  return (New-Object System.Text.UTF8Encoding($false))   # UTF-8 no BOM
}

function New-Backup([string]$p) {
  $ts = (Get-Date).ToString("yyyyMMdd_HHmmss")
  $bak = "$p.bak_$ts"
  Copy-Item -LiteralPath $p -Destination $bak -Force
  return $bak
}

function Get-LatestBackup([string]$p) {
  $dir = Split-Path -Parent $p
  $name = Split-Path -Leaf $p
  $items = Get-ChildItem -LiteralPath $dir -File -Filter ($name + ".bak_*") -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime -Descending
  if ($items -and $items.Count -gt 0) { return $items[0].FullName }
  return ""
}

function Rollback-File([string]$dst, [string]$src) {
  if ([string]::IsNullOrWhiteSpace($src)) { throw "Rollback requested but no backup path provided." }
  if (!(Test-Path -LiteralPath $src)) { throw ("Backup not found: " + $src) }
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Host ("Rollback OK -> " + $src) -ForegroundColor Yellow
}

function Find-IndexMatch($lines, [string]$pattern, [int]$start) {
  for ($i=$start; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match $pattern) { return $i }
  }
  return -1
}

function Replace-Range($lines, [int]$startIdx, [int]$endIdx, $newLines) {
  $before = @()
  if ($startIdx -gt 0) { $before = $lines[0..($startIdx-1)] }
  $after = @()
  if ($endIdx + 1 -le $lines.Count - 1) { $after = $lines[($endIdx+1)..($lines.Count-1)] }
  return @($before + $newLines + $after)
}

if (!(Test-Path -LiteralPath $Path)) { throw ("File not found: " + $Path) }

if ($Rollback) {
  $src = $FromBackup
  if ([string]::IsNullOrWhiteSpace($src)) { $src = Get-LatestBackup $Path }
  Rollback-File -dst $Path -src $src
  exit 0
}

$enc = Get-FileEncoding $Path
$text = [System.IO.File]::ReadAllText($Path, $enc)

# detect newline style
$nl = "`n"
if ($text.Contains("`r`n")) { $nl = "`r`n" }

$bak = New-Backup $Path
Write-Host ("Backup created: " + $bak) -ForegroundColor Cyan

try {
  $lines = @($text -split "\r?\n", 0)

  $idxDef = Find-IndexMatch $lines '^\s*def\s+get_empathy_collection\s*\(\s*\)\s*:\s*$' 0
  if ($idxDef -lt 0) { throw "Could not find: def get_empathy_collection()" }

  # Prefer class boundary, fallback to next top-level def/class
  $idxEnd = Find-IndexMatch $lines '^\s*class\s+EmpathyModule\s*:\s*$' ($idxDef + 1)
  if ($idxEnd -lt 0) {
    $idxEnd = Find-IndexMatch $lines '^\S' ($idxDef + 1)
    if ($idxEnd -lt 0) { throw "Could not find end of get_empathy_collection() block." }
  }

  # If already clean inside the block, no-op
  $block = ($lines[$idxDef..($idxEnd-1)] -join "`n")
  if ($block -notmatch 'PersistentClient') {
    Write-Host "Already OK: no PersistentClient inside get_empathy_collection()." -ForegroundColor Yellow
    exit 0
  }

  $newFunc = @'
def get_empathy_collection():
    """Lazy init. Returns main chroma collection (single-client), or dict fallback."""
    global _EMPATHY_CLIENT, _EMPATHY_COLLECTION
    if _EMPATHY_COLLECTION is not None:
        return _EMPATHY_COLLECTION

    # Single-client mode: use existing global chroma_client only.
    try:
        cc = globals().get("chroma_client")
        if cc is not None:
            _EMPATHY_CLIENT = cc
            _EMPATHY_COLLECTION = cc.get_or_create_collection(EMPATHY_COLLECTION_NAME)
            return _EMPATHY_COLLECTION
    except Exception:
        pass

    # No secondary PersistentClient here.
    _EMPATHY_COLLECTION = {}
    return _EMPATHY_COLLECTION
'@ -split "`n"

  $lines = Replace-Range $lines $idxDef ($idxEnd-1) ($newFunc + @(""))

  $out = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $out, $enc)

  $verify = [System.IO.File]::ReadAllText($Path, $enc)
  if ($verify -notmatch '(?m)^\s*def\s+get_empathy_collection\s*\(\s*\)\s*:') { throw "ASSERT: def get_empathy_collection missing after write." }

  $m = [regex]::Match($verify, '(?ms)^def\s+get_empathy_collection\s*\(\s*\)\s*:.*?(?=^\s*class\s+EmpathyModule\s*:|^\S)', [System.Text.RegularExpressions.RegexOptions]::Multiline)
  if ($m.Success -and $m.Value -match 'PersistentClient') {
    throw "ASSERT: PersistentClient still present inside get_empathy_collection()."
  }

  Write-Host "PATCH OK: get_empathy_collection() -> single-client, removed PersistentClient fallback." -ForegroundColor Green
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback to backup: " + $bak) -ForegroundColor Red
  Rollback-File -dst $Path -src $bak
  throw
}
