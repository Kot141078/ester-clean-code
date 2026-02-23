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
    return (New-Object System.Text.UTF8Encoding($true))  # UTF-8 BOM
  }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFF -and $b[1] -eq 0xFE) {
    return [System.Text.Encoding]::Unicode              # UTF-16 LE
  }
  if ($b.Length -ge 2 -and $b[0] -eq 0xFE -and $b[1] -eq 0xFF) {
    return [System.Text.Encoding]::BigEndianUnicode     # UTF-16 BE
  }
  return (New-Object System.Text.UTF8Encoding($false))  # UTF-8 no BOM
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
  if (!(Test-Path -LiteralPath $src)) { throw "Backup not found: $src" }
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

if (!(Test-Path -LiteralPath $Path)) { throw "File not found: $Path" }

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

  $idxStart = Find-IndexMatch $lines '^\s*def\s+get_empathy_collection\(\):\s*$' 0
  if ($idxStart -lt 0) { throw "Could not find: def get_empathy_collection():" }

  $idxClass = Find-IndexMatch $lines '^\s*class\s+EmpathyModule\s*:\s*$' ($idxStart + 1)
  if ($idxClass -lt 0) { throw "Could not find: class EmpathyModule:" }

  $newBlock = @'
def get_empathy_collection():
    """Single-client mode: reuse ONLY main Chroma client (no secondary PersistentClient)."""
    global _EMPATHY_CLIENT, _EMPATHY_COLLECTION

    # If we already have a real collection (not dict), return it
    if _EMPATHY_COLLECTION is not None and not isinstance(_EMPATHY_COLLECTION, dict):
        return _EMPATHY_COLLECTION

    cc = None

    # Prefer shared/global chroma_client if present
    try:
        cc = globals().get("chroma_client")
    except Exception:
        cc = None

    # Fallback: Hippocampus instance exposes PersistentClient as brain.client
    if cc is None:
        try:
            b = globals().get("brain")
            if b is not None:
                cc = getattr(b, "client", None)
        except Exception:
            cc = None

    if cc is None:
        if _EMPATHY_COLLECTION is None:
            _EMPATHY_COLLECTION = {}
        return _EMPATHY_COLLECTION

    ef = None
    try:
        b = globals().get("brain")
        if b is not None:
            ef = getattr(b, "ef", None)
    except Exception:
        ef = None

    try:
        _EMPATHY_CLIENT = cc
        if ef is not None:
            try:
                _EMPATHY_COLLECTION = cc.get_or_create_collection(EMPATHY_COLLECTION_NAME, embedding_function=ef)
            except TypeError:
                _EMPATHY_COLLECTION = cc.get_or_create_collection(EMPATHY_COLLECTION_NAME)
        else:
            _EMPATHY_COLLECTION = cc.get_or_create_collection(EMPATHY_COLLECTION_NAME)
    except Exception:
        if _EMPATHY_COLLECTION is None:
            _EMPATHY_COLLECTION = {}
    return _EMPATHY_COLLECTION
'@ -split "`n"

  # Replace ONLY the function block; keep class EmpathyModule line intact
  $lines = Replace-Range $lines $idxStart ($idxClass - 1) ($newBlock + @(""))

  $out = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $out, $enc)

  # Assert: ensure no PersistentClient/import chromadb inside the replaced block
  $verify = [System.IO.File]::ReadAllText($Path, $enc)
  $m = [regex]::Match($verify, "(?ms)^def\s+get_empathy_collection\(\):.*?(?=^\s*class\s+EmpathyModule\s*:)")
  if (-not $m.Success) { throw "ASSERT: could not re-locate get_empathy_collection() after write." }
  $body = $m.Value
  if ($body -match "PersistentClient") { throw "ASSERT: PersistentClient still present inside get_empathy_collection()." }
  if ($body -match "(?m)^\s*import\s+chromadb") { throw "ASSERT: import chromadb still present inside get_empathy_collection()." }

  Write-Host "PATCH OK (single-client empathy via chroma_client/brain.client)." -ForegroundColor Cyan
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback to backup: " + $bak) -ForegroundColor Red
  Rollback-File -dst $Path -src $bak
  throw
}
