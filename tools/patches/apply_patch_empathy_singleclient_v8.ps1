param(
  [string]$Path = ".\run_ester_fixed.py",
  [switch]$Rollback,
  [string]$FromBackup = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

function Get-FileEncoding([string]$p) {
  $b = [System.IO.File]::ReadAllBytes($p)
  if ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF) {
    return (New-Object System.Text.UTF8Encoding($true))
  }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) { return [System.Text.Encoding]::Unicode }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFE -and $b[1] -eq 0xFF) { return [System.Text.Encoding]::BigEndianUnicode }
  return (New-Object System.Text.UTF8Encoding($false))
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

function Find-IndexContains($lines, [string]$needle, [int]$start, [int]$endInclusive) {
  $end = [Math]::Min($lines.Count-1, $endInclusive)
  for ($i=$start; $i -le $end; $i++) {
    if ($lines[$i].Contains($needle)) { return $i }
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

# Preserve newline style
$nl = "`n"
if ($text.Contains("`r`n")) { $nl = "`r`n" }

$bak = New-Backup $Path
Write-Host ("Backup created: " + $bak) -ForegroundColor Cyan

try {
  $lines = @($text -split "\r?\n", 0)

  $idxDef = Find-IndexMatch $lines '^\s*def\s+get_empathy_collection\s*\(\s*\)\s*:\s*$' 0
  if ($idxDef -lt 0) { throw "Could not find: def get_empathy_collection():" }

  $idxClass = Find-IndexMatch $lines '^\s*class\s+EmpathyModule\s*:\s*$' ($idxDef + 1)
  if ($idxClass -lt 0) { throw "Could not find: class EmpathyModule:" }

  $funcStart = $idxDef
  $funcEnd = $idxClass - 1

  # Find anchor inside function: prefer PersistentClient line, fallback to import chromadb
  $idxPC = Find-IndexContains $lines 'chromadb.PersistentClient' ($funcStart+1) $funcEnd
  $idxImp = Find-IndexContains $lines 'import chromadb' ($funcStart+1) $funcEnd
  if ($idxPC -lt 0 -and $idxImp -lt 0) {
    Write-Host "Already OK: no secondary PersistentClient/import chromadb inside get_empathy_collection()." -ForegroundColor Yellow
    exit 0
  }

  $anchor = $idxPC
  if ($anchor -lt 0) { $anchor = $idxImp }

  # Find the try: line above anchor
  $idxTry = -1
  for ($i=$anchor; $i -ge $funcStart; $i--) {
    if ($lines[$i] -match '^\s*try:\s*$') { $idxTry = $i; break }
  }
  if ($idxTry -lt 0) { throw "Could not locate try: block inside get_empathy_collection()." }

  # Find the return _EMPATHY_COLLECTION below anchor (end of fallback)
  $idxRet = -1
  for ($i=$anchor; $i -le $funcEnd; $i++) {
    if ($lines[$i] -match '^\s*return\s+_EMPATHY_COLLECTION\s*$') { $idxRet = $i; break }
  }
  if ($idxRet -lt 0) { throw "Could not locate: return _EMPATHY_COLLECTION inside get_empathy_collection()." }

  $indent = ($lines[$idxTry] -replace '^(\s*).*$','$1')

  $replacement = @(
    ($indent + "# Single-client rule: do NOT create a secondary chroma client here."),
    ($indent + "_EMPATHY_COLLECTION = {}"),
    ($indent + "return _EMPATHY_COLLECTION")
  )

  $lines = Replace-Range $lines $idxTry $idxRet $replacement

  $out = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $out, $enc)

  # Verify INSIDE function block only
  $verifyLines = @([System.IO.File]::ReadAllText($Path, $enc) -split "\r?\n", 0)
  $vd = Find-IndexMatch $verifyLines '^\s*def\s+get_empathy_collection\s*\(\s*\)\s*:\s*$' 0
  $vc = Find-IndexMatch $verifyLines '^\s*class\s+EmpathyModule\s*:\s*$' ($vd + 1)
  if ($vd -lt 0 -or $vc -lt 0) { throw "ASSERT: could not re-locate empathy block after write." }

  $hasPC = Find-IndexContains $verifyLines 'chromadb.PersistentClient' $vd ($vc-1)
  $hasImp = Find-IndexContains $verifyLines 'import chromadb' $vd ($vc-1)
  if ($hasPC -ge 0) { throw "ASSERT: chromadb.PersistentClient still present inside get_empathy_collection()." }
  if ($hasImp -ge 0) { throw "ASSERT: import chromadb still present inside get_empathy_collection()." }

  Write-Host "PATCH OK: empathy fallback no longer creates second PersistentClient (single-client mode)." -ForegroundColor Green
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback to backup: " + $bak) -ForegroundColor Red
  Rollback-File -dst $Path -src $bak
  throw
}
