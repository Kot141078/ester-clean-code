param(
  [string]$Path = ".\run_ester_fixed.py",
  [switch]$Rollback,
  [string]$FromBackup = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

# ============================================================
# EXPLICIT BRIDGE: c=a+b -> stable memory procedure (b) must reuse the same storage substrate as cognition (b) + human signal (a)
# HIDDEN BRIDGE 1 (Ashby): reduce uncontrolled variety (multiple clients) -> keep variety in content, not in storage handles
# HIDDEN BRIDGE 2 (Cover&Thomas): avoid redundant channels/handles -> one client, many collections, bounded overhead
# EARTH (engineering): two open file-backed DB clients to same path is like two drivers grabbing the same steering wheel.
# ============================================================

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

  # end at next top-level class definition
  $idxEnd = -1
  for ($i=$idxStart+1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*class\s+\w+\s*:' -and $lines[$i] -notmatch '^\s{4,}class\s+') {
      $idxEnd = $i - 1
      break
    }
  }
  if ($idxEnd -lt $idxStart) { throw "Could not find end boundary after get_empathy_collection() (next class)." }

  # If already single-client (no extra PersistentClient inside this function), skip
  $funcText = ($lines[$idxStart..$idxEnd] -join "`n")
  if ($funcText -notmatch 'PersistentClient' -and $funcText -notmatch 'import\s+chromadb') {
    Write-Host "Looks already single-client (no PersistentClient/import chromadb inside get_empathy_collection). Nothing to do." -ForegroundColor Yellow
    exit 0
  }

  $newFunc = @'
def get_empathy_collection():
    """Lazy init. Single-client mode: reuse ONLY main Chroma client (no secondary PersistentClient)."""
    global _EMPATHY_CLIENT, _EMPATHY_COLLECTION

    if _EMPATHY_COLLECTION is not None:
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
        _EMPATHY_COLLECTION = {}
        return _EMPATHY_COLLECTION

    # Try to reuse the same embedding function (keeps collection schema consistent)
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
        _EMPATHY_COLLECTION = {}

    return _EMPATHY_COLLECTION
'@ -split "`n"

  $lines = Replace-Range $lines $idxStart $idxEnd ($newFunc + @(""))

  $out = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $out, $enc)

  # Assertions: ensure function no longer imports chromadb / creates PersistentClient
  $verify = [System.IO.File]::ReadAllText($Path, $enc)
  $m = [regex]::Match($verify, "(?ms)^def\s+get_empathy_collection\(\):.*?(?=^\s*class\s+\w+\s*:)")
  if (-not $m.Success) { throw "ASSERT: could not re-locate get_empathy_collection() after write." }
  $body = $m.Value
  if ($body -match "import\s+chromadb") { throw "ASSERT: import chromadb still present inside get_empathy_collection()." }
  if ($body -match "PersistentClient") { throw "ASSERT: PersistentClient still present inside get_empathy_collection()." }

  Write-Host "PATCH OK (single-client empathy)." -ForegroundColor Cyan
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback to backup: " + $bak) -ForegroundColor Red
  Rollback-File -dst $Path -src $bak
  throw
}
