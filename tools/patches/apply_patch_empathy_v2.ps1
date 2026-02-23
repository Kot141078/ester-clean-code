param(
  [string]$Path = ".\run_ester_fixed.py",
  [switch]$Rollback,
  [string]$FromBackup = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = "Stop"

# ============================================================
# EXPLICIT BRIDGE: c=a+b -> human affect signal (a) gated by stable procedures (b)
# HIDDEN BRIDGE 1 (Ashby): more variety in affect sensing, but clamp behavior for stability
# HIDDEN BRIDGE 2 (Cover&Thomas): compact affect telemetry, capped history to protect bandwidth
# EARTH: emotions are sensors; executive control is the actuator (do not swap roles)
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

# Newline style
$nl = "`n"
if ($text.Contains("`r`n")) { $nl = "`r`n" }

# Prevent double-apply
if ($text -match "(?m)^\s*def\s+get_empathy_collection\(") {
  throw "Patch looks already applied (get_empathy_collection found)."
}
if ($text -match "(?m)^\s*def\s+_should_use_emotional_mode\(") {
  throw "Patch looks already applied (_should_use_emotional_mode found)."
}

$bak = New-Backup $Path
Write-Host ("Backup created: " + $bak) -ForegroundColor Cyan

try {
  $lines = @($text -split "\r?\n", 0)

  # ------------------------------------------------------------
  # 1) Replace empathy_collection init block (non-persistent) with persistent lazy getter
  # ------------------------------------------------------------
  $idxNeedle = Find-IndexContains $lines 'empathy_collection = chroma_client.get_or_create_collection("ester_empathy")' 0
  if ($idxNeedle -lt 0) { throw "Step1: could not find empathy_collection init line." }

  $start = -1
  for ($i=$idxNeedle; $i -ge [Math]::Max(0, $idxNeedle-40); $i--) {
    if ($lines[$i].Trim() -eq "try:") {
      $j = $i + 1
      while ($j -lt $lines.Count -and $lines[$j].Trim() -eq "") { $j++ }
      if ($j -lt $lines.Count -and $lines[$j].Contains("import chromadb")) { $start = $i; break }
    }
  }
  if ($start -lt 0) { throw "Step1: could not locate start of try/import chromadb block." }

  $end = -1
  for ($i=$idxNeedle; $i -lt [Math]::Min($lines.Count, $idxNeedle+40); $i++) {
    if ($lines[$i].Contains("empathy_collection = {}")) { $end = $i; break }
  }
  if ($end -lt 0) { throw "Step1: could not locate end of empathy_collection block." }

  $helper = @'
# --- Empathy storage (persistent) ---
EMPATHY_V2_ENABLED = (os.getenv("ESTER_EMPATHY_V2", "1").strip().lower() not in ("0", "false", "no", "off"))
EMPATHY_COLLECTION_NAME = os.getenv("ESTER_EMPATHY_COLLECTION", "ester_empathy")
EMPATHY_HISTORY_MAX = int(os.getenv("ESTER_EMPATHY_HISTORY_MAX", "100"))

_EMPATHY_CLIENT = None
_EMPATHY_COLLECTION = None

def _resolve_empathy_persist_dir() -> str:
    """Best-effort persistent directory for empathy storage."""
    try:
        p = globals().get("VECTOR_DB_PATH")
        if p:
            return str(p)
    except Exception:
        pass
    raw = (os.getenv("CHROMA_PERSIST_DIR") or "").strip()
    if raw:
        raw = os.path.expandvars(os.path.expanduser(raw))
        try:
            return str(Path(raw).resolve())
        except Exception:
            return raw
    base = (os.getenv("ESTER_HOME") or "").strip()
    if not base:
        base = os.getcwd()
    base = os.path.expandvars(os.path.expanduser(base))
    try:
        base = str(Path(base).resolve())
    except Exception:
        pass
    return str(Path(base) / "vstore" / "chroma")

def get_empathy_collection():
    """Lazy init. Returns chroma collection or dict fallback."""
    global _EMPATHY_CLIENT, _EMPATHY_COLLECTION
    if _EMPATHY_COLLECTION is not None:
        return _EMPATHY_COLLECTION

    # Prefer main chroma_client if available
    try:
        cc = globals().get("chroma_client")
        if cc is not None:
            _EMPATHY_CLIENT = cc
            _EMPATHY_COLLECTION = cc.get_or_create_collection(EMPATHY_COLLECTION_NAME)
            return _EMPATHY_COLLECTION
    except Exception:
        pass

    try:
        import chromadb
        persist_dir = _resolve_empathy_persist_dir()
        os.makedirs(persist_dir, exist_ok=True)
        _EMPATHY_CLIENT = chromadb.PersistentClient(path=persist_dir)
        _EMPATHY_COLLECTION = _EMPATHY_CLIENT.get_or_create_collection(EMPATHY_COLLECTION_NAME)
    except Exception:
        _EMPATHY_COLLECTION = {}
    return _EMPATHY_COLLECTION
'@ -split "`n"

  $lines = Replace-Range $lines $start $end $helper
  Write-Host "Step1 OK: empathy storage -> persistent lazy getter." -ForegroundColor Green

  # ------------------------------------------------------------
  # 2) Insert emotional gating helpers before dummy_llm_analyze_tone
  # ------------------------------------------------------------
  $idxDummy = Find-IndexMatch $lines '^\s*def\s+dummy_llm_analyze_tone\(' 0
  if ($idxDummy -lt 0) { throw "Step2: could not find dummy_llm_analyze_tone." }

  $gating = @'
# --- Emotional mode gating (v2) ---
EMO_STICKY_SECONDS = int(os.getenv("ESTER_EMO_STICKY_SECONDS", "600"))
_EMO_STICKY_UNTIL = 0.0

def _is_technical_text(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    if "traceback" in low or "syntaxerror" in low or "exception" in low:
        return True
    if "ps " in low or "powershell" in low:
        return True
    if "```" in t:
        return True
    if re.search(r"(^|\n)\s*(ps\s+[a-z]:\\|[a-z]:\\|/mnt/|/home/|/var/)", low):
        return True
    if re.search(r"\b(def|class|import|pip|conda|docker|http|https)\b", low):
        return True
    if re.search(r"\b(error|failed|warning|stack|kernel|driver|gpu|cuda|chroma|chromadb)\b", low):
        return True
    return False

def _should_use_emotional_mode(user_text: str, identity_prompt: str) -> bool:
    """Sticky emotional mode for Owner, with technical override."""
    global _EMO_STICKY_UNTIL
    is_ivan = ("\u0418\u0412\u0410\u041d" in (identity_prompt or "").upper())
    if not is_ivan:
        return False
    # Slot A: legacy behavior
    if not EMPATHY_V2_ENABLED:
        return bool(_is_emotional_text(user_text))
    # Slot B: improved gating
    if _is_technical_text(user_text):
        _EMO_STICKY_UNTIL = 0.0
        return False
    now = time.time()
    if _is_emotional_text(user_text):
        _EMO_STICKY_UNTIL = now + max(0, int(EMO_STICKY_SECONDS))
        return True
    if now < _EMO_STICKY_UNTIL:
        return True
    return False

def _emotion_telemetry(user_text: str) -> str:
    """Compact affect signal (telemetry)."""
    if not EMPATHY_V2_ENABLED:
        return ""
    try:
        scores = analyze_emotions(user_text, user_ctx=None) or {}
    except Exception:
        return ""
    items = []
    for k, v in scores.items():
        if isinstance(v, (int, float)):
            items.append((str(k), float(v)))
    items.sort(key=lambda x: x[1], reverse=True)
    items = items[:4]
    return ", ".join([f"{k}={v:.2f}" for k, v in items])
'@ -split "`n"

  $lines = @($lines[0..($idxDummy-1)] + @("") + $gating + @("") + $lines[$idxDummy..($lines.Count-1)])
  Write-Host "Step2 OK: inserted emotional gating helpers." -ForegroundColor Green

  # ------------------------------------------------------------
  # 3) Replace is_ivan + emotional_mode lines in ester_arbitrage with improved gating
  # ------------------------------------------------------------
  $idxEmo = Find-IndexContains $lines "emotional_mode = bool(is_ivan and _is_emotional_text(user_text))" 0
  if ($idxEmo -lt 1) { throw "Step3: could not find emotional_mode assignment line." }
  $idxOwner = $idxEmo - 1
  if (-not $lines[$idxOwner].Contains("is_ivan") -or -not $lines[$idxOwner].Contains("identity_prompt")) {
    throw "Step3: could not confirm is_ivan line right above emotional_mode."
  }
  $indent = ($lines[$idxOwner] -replace "^(\s*).*$", '$1')
  $lines[$idxOwner] = ($indent + "emotional_mode = _should_use_emotional_mode(user_text, identity_prompt)")
  $lines[$idxEmo]  = ($indent + "aff_signal = _emotion_telemetry(user_text)")
  Write-Host "Step3 OK: ester_arbitrage emotional_mode -> sticky gating + aff_signal." -ForegroundColor Green

  # ------------------------------------------------------------
  # 4) Insert [AFFECT_SIGNAL] block right after people_context line in system prompt f-string
  # ------------------------------------------------------------
  $idxPeople = -1
  for ($i=0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Contains("{people_context") -and $lines[$i].Contains('or "')) { $idxPeople = $i; break }
  }
  if ($idxPeople -lt 0) { throw "Step4: could not find people_context line." }
  $ind2 = ($lines[$idxPeople] -replace "^(\s*).*$", '$1')
  $insert = @(
    "",
    ($ind2 + "[AFFECT_SIGNAL]:"),
    ($ind2 + '{aff_signal or "n/a"}')
  )
  $lines = Insert-After $lines $idxPeople $insert
  Write-Host "Step4 OK: inserted [AFFECT_SIGNAL] block." -ForegroundColor Green

  # ------------------------------------------------------------
  # 5) Cap empathy history after append in analyze_user_message
  # ------------------------------------------------------------
  $idxAppend = Find-IndexContains $lines 'self.user_history.append({"message": message, "analysis": analysis})' 0
  if ($idxAppend -ge 0) {
    $ind3 = ($lines[$idxAppend] -replace "^(\s*).*$", '$1')
    $cap = @(
      ($ind3 + "if EMPATHY_V2_ENABLED and EMPATHY_HISTORY_MAX > 0:"),
      ($ind3 + "    self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]")
    )
    $lines = Insert-After $lines $idxAppend $cap
    Write-Host "Step5 OK: capped empathy history." -ForegroundColor Green
  } else {
    Write-Host "Step5 skipped: append line not found." -ForegroundColor Yellow
  }

  # ------------------------------------------------------------
  # 6) Replace save_to_db/load_from_db to use get_empathy_collection() + upsert (with fallback) + cap
  # ------------------------------------------------------------
  $idxSave = Find-IndexMatch $lines '^\s{4}def\s+save_to_db\(self\):' 0
  $idxDaily = Find-IndexMatch $lines '^\s*def\s+_is_daily_contacts_query\(' 0
  if ($idxSave -lt 0 -or $idxDaily -lt 0 -or $idxDaily -le $idxSave) {
    throw "Step6: could not locate save_to_db block or daily query function."
  }

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

  $lines = Replace-Range $lines $idxSave ($idxDaily-1) ($newSaveLoad + @(""))
  Write-Host "Step6 OK: save/load -> persistent collection + upsert + cap." -ForegroundColor Green

  # ------------------------------------------------------------
  # Write back (preserve encoding)
  # ------------------------------------------------------------
  $out = ($lines -join $nl)
  [System.IO.File]::WriteAllText($Path, $out, $enc)

  # Simple assertions
  $out2 = [System.IO.File]::ReadAllText($Path, $enc)
  if ($out2.IndexOf("def get_empathy_collection", [System.StringComparison]::Ordinal) -lt 0) { throw "ASSERT: get_empathy_collection missing after write." }
  if ($out2.IndexOf("def _should_use_emotional_mode", [System.StringComparison]::Ordinal) -lt 0) { throw "ASSERT: _should_use_emotional_mode missing after write." }
  if ($out2.IndexOf("[AFFECT_SIGNAL]", [System.StringComparison]::Ordinal) -lt 0) { throw "ASSERT: [AFFECT_SIGNAL] block missing after write." }

  Write-Host "PATCH OK." -ForegroundColor Cyan
}
catch {
  Write-Host ("Patch FAILED -> auto-rollback to backup: " + $bak) -ForegroundColor Red
  Rollback-File -dst $Path -src $bak
  throw
}
