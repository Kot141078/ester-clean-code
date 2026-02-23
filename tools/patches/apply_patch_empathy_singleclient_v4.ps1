param(
  [string]$Path = ".\run_ester_fixed.py",
  [switch]$Rollback,
  [string]$FromBackup = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

# ============================================================
# EXPLICIT BRIDGE: c=a+b -> stable shared memory client (b) for personal continuity (c)
# HIDDEN BRIDGE 1 (Ashby): avoid extra client variety that increases brittleness (locks/races)
# HIDDEN BRIDGE 2 (Cover&Thomas): cap history to protect bandwidth/latency
# EARTH: one "heart" (one client) pumping; multiple hearts = arrhythmia
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

function Find-IndexContains($lines, [string]$needle, [int]$start) {
  for ($i=$start; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Contains($needle)) { return $i }
  }
  return -1
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

function Insert-After($lines, [int]$idx, $toInsert) {
  $before = @()
  if ($idx -ge 0) { $before = $lines[0..$idx] }
  $after = @()
  if ($idx + 1 -le $lines.Count - 1) { $after = $lines[($idx+1)..($lines.Count-1)] }
  return @($before + $toInsert + $after)
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

$nl = "`n"
if ($text.Contains("`r`n")) { $nl = "`r`n" }

$bak = New-Backup $Path
Write-Host ("Backup created: " + $bak) -ForegroundColor Cyan

try {
  $lines = @($text -split "\r?\n", 0)

  # ------------------------------------------------------------
  # STEP 1: Remove empathy's own chromadb.Client() init block
  # Find the needle line that exists in your current file.
  # ------------------------------------------------------------
  $idxNeedle = Find-IndexContains $lines 'empathy_collection = chroma_client.get_or_create_collection("ester_empathy")' 0
  if ($idxNeedle -lt 0) { throw "Step1: could not find empathy_collection init line (needle missing)." }

  # Find start: "try:" with "import chromadb" right after (within ~40 lines back)
  $start = -1
  for ($i=$idxNeedle; $i -ge [Math]::Max(0, $idxNeedle-60); $i--) {
    if ($lines[$i].Trim() -eq "try:") {
      $j = $i + 1
      while ($j -lt $lines.Count -and $lines[$j].Trim() -eq "") { $j++ }
      if ($j -lt $lines.Count -and $lines[$j].Contains("import chromadb")) { $start = $i; break }
    }
  }
  if ($start -lt 0) { throw "Step1: could not locate start of try/import chromadb block." }

  # Find end: line containing empathy_collection = {} (within ~60 lines forward)
  $end = -1
  for ($i=$idxNeedle; $i -lt [Math]::Min($lines.Count, $idxNeedle+80); $i++) {
    if ($lines[$i].Contains("empathy_collection = {}")) { $end = $i; break }
  }
  if ($end -lt 0) { throw "Step1: could not locate end of empathy_collection block." }

  # Replacement: shared-client helper (NO second chroma client)
  $helper = @'
# --- Empathy storage (single-client: use Hippocampus/brain.client only) ---
EMPATHY_V2_ENABLED = (os.getenv("ESTER_EMPATHY_V2", "1").strip().lower() not in ("0", "false", "no", "off"))
EMPATHY_COLLECTION_NAME = os.getenv("ESTER_EMPATHY_COLLECTION", "ester_empathy")
EMPATHY_HISTORY_MAX = int(os.getenv("ESTER_EMPATHY_HISTORY_MAX", "100"))

_EMPATHY_FALLBACK = {}

def get_empathy_collection():
    """
    Single-client rule:
      - Use brain.client (PersistentClient) if available.
      - Never create a second chroma client here.
      - Fallback: in-memory dict.
    """
    try:
        b = globals().get("brain")
        if b is not None:
            c = getattr(b, "client", None)
            ef = getattr(b, "ef", None)
            if c is not None:
                try:
                    return c.get_or_create_collection(name=EMPATHY_COLLECTION_NAME, embedding_function=ef)
                except TypeError:
                    return c.get_or_create_collection(name=EMPATHY_COLLECTION_NAME)
    except Exception:
        pass
    return _EMPATHY_FALLBACK

# legacy placeholder (should not be used directly anymore)
empathy_collection = None
'@ -split "`n"

  $lines = Replace-Range $lines $start $end $helper
  Write-Host "Step1 OK: removed second chroma client; added get_empathy_collection() single-client." -ForegroundColor Green

  # ------------------------------------------------------------
  # STEP 2: Cap history after append in EmpathyModule (if that line exists)
  # ------------------------------------------------------------
  $idxAppend = Find-IndexContains $lines 'self.user_history.append({"message": message, "analysis": analysis})' 0
  if ($idxAppend -ge 0) {
    # Avoid double insert
    $already = $false
    for ($k=$idxAppend+1; $k -le [Math]::Min($lines.Count-1, $idxAppend+6); $k++) {
      if ($lines[$k].Contains("self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]")) { $already = $true; break }
    }
    if (-not $already) {
      $ind = ($lines[$idxAppend] -replace "^(\s*).*$", '$1')
      $cap = @(
        ($ind + "if EMPATHY_V2_ENABLED and EMPATHY_HISTORY_MAX > 0:"),
        ($ind + "    self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]")
      )
      $lines = Insert-After $lines $idxAppend $cap
      Write-Host "Step2 OK: inserted empathy history cap." -ForegroundColor Green
    } else {
      Write-Host "Step2 skipped: cap already present." -ForegroundColor Yellow
    }
  } else {
    Write-Host "Step2 skipped: append line not found." -ForegroundColor Yellow
  }

  # ------------------------------------------------------------
  # STEP 3: Replace EmpathyModule save_to_db/load_from_db to use get_empathy_collection() + upsert
  # ------------------------------------------------------------
  $idxSave = Find-IndexMatch $lines '^\s{4}def\s+save_to_db\(self\):' 0
  if ($idxSave -lt 0) { throw "Step3: could not find EmpathyModule.save_to_db." }

  # Find first top-level def after idxSave (indent 0)
  $idxNextTop = -1
  for ($i=$idxSave+1; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*def\s+' -and ($lines[$i] -notmatch '^\s{4}def\s+')) {
      $idxNextTop = $i
      break
    }
  }
  if ($idxNextTop -lt 0) { throw "Step3: could not find next top-level def after EmpathyModule." }

  $newSaveLoad = @'
    def save_to_db(self):
        """Persist empathy history (best-effort)."""
        try:
            data = json.dumps(self.user_history)
        except Exception:
            data = "[]"
        metadata = {"user_id": self.user_id, "timestamp": time.time(), "type": "empathy_history"}
        coll = get_empathy_collection()
        if isinstance(coll, dict):
            coll[self.user_id] = data
        else:
            # Prefer upsert; fallback to delete+add for older chroma builds
            try:
                coll.upsert(documents=[data], metadatas=[metadata], ids=[self.user_id])
            except Exception:
                try:
                    coll.delete(ids=[self.user_id])
                except Exception:
                    pass
                coll.add(documents=[data], metadatas=[metadata], ids=[self.user_id])

    def load_from_db(self):
        """Load empathy history (best-effort)."""
        coll = get_empathy_collection()
        try:
            if isinstance(coll, dict):
                if self.user_id in coll:
                    self.user_history = json.loads(coll[self.user_id]) or []
            else:
                result = coll.get(ids=[self.user_id])
                docs = (result.get("documents") or []) if isinstance(result, dict) else []
                if docs:
                    self.user_history = json.loads(docs[0]) or []
        except Exception:
            self.user_history = []
        if EMPATHY_V2_ENABLED and EMPATHY_HISTORY_MAX > 0:
            self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]
'@ -split "`n"

  $lines = Replace-Range $lines $idxSave ($idxNextTop-1) ($newSaveLoad + @(""))
  Write-Host "Step3 OK: save/load now uses single-client collection + upsert + cap." -ForegroundColor Green

  # ------------------------------------------------------------
  # Write back
  # ------------------------------------------------------------
  $out = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $out, $enc)

  # Assertions (quick)
  $check = [System.IO.File]::ReadAllText($Path, $enc)
  if ($check.IndexOf("def get_empathy_collection", [System.StringComparison]::Ordinal) -lt 0) { throw "ASSERT: get_empathy_collection missing." }
  if ($check.IndexOf("Single-client rule", [System.StringComparison]::Ordinal) -lt 0) { throw "ASSERT: single-client helper block missing." }

  Write-Host "PATCH OK." -ForegroundColor Cyan
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback to backup: " + $bak) -ForegroundColor Red
  Rollback-File -dst $Path -src $bak
  throw
}
