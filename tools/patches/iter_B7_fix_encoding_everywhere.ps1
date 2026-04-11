# iter_B7_fix_encoding_everywhere.ps1  (B7c, PowerShell 5-safe)
# Encoding hygiene end-to-end: normalize at boundaries (TG in/out + passport write/read) + optional passport sanitize.
#
# Explicit bridge: c=a+b -> (a) text/memory + (c) normalization at the boundaries => (c) long-term memory without gibberish.
# Hidden bridges: Ashby (several transcoding hypotheses), Carpet&Thomas (channel noise immunity), Gray's (seam on the I/O border).
# Erth: like a filter at the ventilation inlet - we place it at the boundaries so that dirt does not fly into the “lungs” of long-term memory.

param(
  [switch]$SanitizePassport
)

$ErrorActionPreference = "Stop"

function Write-Ok($s){ Write-Host "[OK] $s" -ForegroundColor Green }
function Write-Warn($s){ Write-Host "[WARN] $s" -ForegroundColor Yellow }
function Write-Info($s){ Write-Host "[info] $s" -ForegroundColor Cyan }
function Write-Err($s){ Write-Host "[ERR] $s" -ForegroundColor Red }

function Get-NL([string]$t){
  if ($t -match "`r`n") { return "`r`n" }
  return "`n"
}

function Read-Utf8NoBom([string]$path){
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  return [System.IO.File]::ReadAllText($path, $utf8)
}

function Write-Utf8NoBom([string]$path, [string]$text){
  $utf8 = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($path, $text, $utf8)
}

function Replace-First([string]$text, [string]$pattern, [string]$replacement){
  $re = New-Object System.Text.RegularExpressions.Regex($pattern, [System.Text.RegularExpressions.RegexOptions]::Multiline)
  $m = $re.Match($text)
  if (!$m.Success) { return $null }
  return ($re.Replace($text, $replacement, 1))
}

function Insert-Normalize-InFunc([string]$src, [string]$funcName, [string[]]$bodyLinesToInsert){
  $nl = Get-NL $src
  $lines = $src -split "\r?\n", -1

  # find def line
  $idx = -1
  for ($i=0; $i -lt $lines.Length; $i++){
    if ($lines[$i] -match ("^\s*def\s+" + [Regex]::Escape($funcName) + "\s*\(")){
      $idx = $i; break
    }
  }
  if ($idx -lt 0){ return @{ ok=$false; src=$src; why="def not found" } }

  # determine indent
  $m = [Regex]::Match($lines[$idx], "^(\s*)def\s+")
  $indent = $m.Groups[1].Value
  $bodyIndent = $indent + "    "

  # detect if already has _normalize_text in first ~80 lines of function
  $already = $false
  for ($t=$idx+1; $t -lt [Math]::Min($lines.Length, $idx+90); $t++){
    if ($lines[$t] -match "^\s*def\s+") { break }
    if ($lines[$t] -match "_normalize_text\("){ $already = $true; break }
  }
  if ($already){
    return @{ ok=$true; src=$src; why="already" }
  }

  # find insertion point: after docstring if present
  $j = $idx + 1
  while ($j -lt $lines.Length -and $lines[$j].Trim() -eq "") { $j++ }

  if ($j -lt $lines.Length){
    $trim = $lines[$j].TrimStart()
    $q = $null
    if ($trim.StartsWith('"""')) { $q='"""' }
    elseif ($trim.StartsWith("'''")) { $q="'''" }

    if ($q -ne $null){
      # docstring may close on same line
      $rest = $trim.Substring(3)
      if ($rest.Contains($q)){
        $j = $j + 1
      } else {
        $k = $j + 1
        while ($k -lt $lines.Length){
          if ($lines[$k].Contains($q)){
            $k = $k + 1
            break
          }
          $k++
        }
        $j = $k
      }
    }
  }

  # build insert lines with indent
  $ins = New-Object System.Collections.Generic.List[string]
  foreach($l in $bodyLinesToInsert){
    $ins.Add($bodyIndent + $l) | Out-Null
  }

  $lst = New-Object System.Collections.Generic.List[string]
  foreach($ln in $lines){ $lst.Add($ln) | Out-Null }

  if ($j -gt $lst.Count){ $j = $lst.Count }
  $lst.InsertRange($j, $ins)

  $out = [string]::Join($nl, $lst.ToArray())
  return @{ ok=$true; src=$out; why="inserted" }
}

# --- Paths
$proj = (Get-Location).Path
$run  = Join-Path $proj "run_ester_fixed.py"
if (!(Test-Path $run)) { throw "Ne nayden run_ester_fixed.py. Snachala: cd <repo-root>" }

$pyVenv = Join-Path $proj ".venv\Scripts\python.exe"
$py = $null
if (Test-Path $pyVenv) { $py = $pyVenv } else { $py = "python" }

# --- Backup
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$bak = "$run.bak_$ts"
Copy-Item $run $bak -Force
Write-Ok "Backup: $bak"

try {
  $src = Read-Utf8NoBom $run
  $nl = Get-NL $src

  # 1) ensure import unicodedata
  if ($src -notmatch "(?m)^\s*import\s+unicodedata\s*$") {
    $try = Replace-First $src '(?m)^\s*import\s+traceback\s*$' ("import traceback" + $nl + "import unicodedata")
    if ($try -eq $null) { $try = Replace-First $src '(?m)^\s*import\s+logging\s*$' ("import logging" + $nl + "import unicodedata") }
    if ($try -eq $null) { throw "Ne nashel anchor dlya vstavki 'import unicodedata'." }
    $src = $try
    Write-Ok "Inserted: import unicodedata"
  } else {
    Write-Info "import unicodedata already present"
  }

  # 2) insert helpers block before _persist_to_passport (idempotent)
  if ($src -notmatch "# === Encoding hygiene \(B7\) BEGIN ===") {
    $block = @"
# === Encoding hygiene (B7) BEGIN ===
def _redecode_utf8(_s: str, _src_enc: str):
    try:
        return _s.encode(_src_enc).decode("utf-8")
    except Exception:
        return None

def _looks_mojibake(_s: str) -> bool:
    if not _s:
        return False
    if "vЂ" in _s or "vњ" in _s or "â€" in _s:
        return True
    if "Ð" in _s or "Ñ" in _s:
        return True
    _n = len(_s)
    if _n >= 20:
        _rs = (_s.count("R") + _s.count("S")) / float(_n)
        if _rs > 0.18:
            return True
    return False

def _encoding_score(_s: str) -> int:
    if not _s:
        return -10**9
    _cyr = 0
    _latin1 = 0
    _bad = 0
    for ch in _s:
        o = ord(ch)
        if 0x0400 <= o <= 0x04FF:
            _cyr += 1
        elif 0x00A0 <= o <= 0x00FF:
            _latin1 += 1
        elif ch == "\ufffd":
            _bad += 5
    if "vЂ" in _s: _bad += 20
    if "vњ" in _s: _bad += 20
    if "â€" in _s: _bad += 20
    if "Ð" in _s or "Ñ" in _s: _bad += 20
    return (_cyr * 3) - (_latin1 * 2) - (_bad * 5)

def _normalize_text(x):
    if x is None:
        return x
    if isinstance(x, bytes):
        for enc in ("utf-8", "cp1251", "latin1", "cp1252", "cp866"):
            try:
                x = x.decode(enc)
                break
            except Exception:
                pass
        if isinstance(x, bytes):
            try:
                x = x.decode("utf-8", errors="replace")
            except Exception:
                return x
    if not isinstance(x, str):
        return x
    s = unicodedata.normalize("NFC", x)
    if not _looks_mojibake(s):
        return s
    best = s
    best_sc = _encoding_score(best)
    for enc in ("cp1251", "latin1", "cp1252", "cp866"):
        cand = _redecode_utf8(s, enc)
        if cand is None:
            continue
        cand = unicodedata.normalize("NFC", cand)
        sc = _encoding_score(cand)
        if sc > best_sc:
            best, best_sc = cand, sc
    return best

def _normalize_obj(obj):
    if obj is None:
        return obj
    if isinstance(obj, (str, bytes)):
        return _normalize_text(obj)
    if isinstance(obj, list):
        return [_normalize_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_normalize_obj(v) for v in obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            nk = _normalize_text(k) if isinstance(k, (str, bytes)) else k
            out[nk] = _normalize_obj(v)
        return out
    return obj
# === Encoding hygiene (B7) END ===

"@
    $ins = Replace-First $src '(?m)^\s*def\s+_persist_to_passport\s*\(' ($block + "def _persist_to_passport(")
    if ($ins -eq $null) { throw "Ne nashel def _persist_to_passport dlya vstavki bloka B7." }
    $src = $ins
    Write-Ok "Inserted encoding hygiene helpers (B7)"
  } else {
    Write-Info "Encoding hygiene block already present"
  }

  # 3) patch _persist_to_passport BODY (signature-agnostic, docstring-safe)
  $res = Insert-Normalize-InFunc $src "_persist_to_passport" @(
    'try:',
    '    role = _normalize_text(role)',
    'except Exception:',
    '    pass',
    'try:',
    '    content = _normalize_text(content)',
    'except Exception:',
    '    pass'
  )
  if (-not $res.ok) { throw "Ne nashel funktsiyu _persist_to_passport (def ...)." }
  $src = $res.src
  if ($res.why -eq "inserted") { Write-Ok "_persist_to_passport: inserted normalization (body)" } else { Write-Info "_persist_to_passport: already normalized" }

  # 4) json.dumps(rec, ensure_ascii=False) -> json.dumps(_normalize_obj(rec), ensure_ascii=False)
  if ($src -match 'json\.dumps\(rec,\s*ensure_ascii=False\)') {
    $src = $src -replace 'json\.dumps\(rec,\s*ensure_ascii=False\)', 'json.dumps(_normalize_obj(rec), ensure_ascii=False)'
    Write-Ok "_persist_to_passport: json.dumps uses _normalize_obj(rec) (global exact replace)"
  } else {
    Write-Info "json.dumps(rec, ensure_ascii=False) not found (maybe already patched)"
  }

  # 5) best-effort: restore_context_from_passport normalize (anchor may differ)
  if ($src -notmatch '(?m)^\s*content\s*=\s*_normalize_text\(content\)\s*$') {
    $needle = '^\s*role_user\s*=\s*rec\.get\(\s*[''"]role_user[''"]\s*,\s*[''"]user[''"]\s*\)\s*$'
    $rep = @(
      '        role_user = rec.get("role_user", "user")',
      '        role_assistant = rec.get("role_assistant", "assistant")',
      '        content = rec.get("content", "")',
      '        role_user = _normalize_text(role_user)',
      '        role_assistant = _normalize_text(role_assistant)',
      '        content = _normalize_text(content)'
    ) -join $nl

    $src2 = Replace-First $src $needle $rep
    if ($src2 -ne $null) {
      $src = $src2
      Write-Ok "restore_context_from_passport: inserted normalization"
    } else {
      Write-Warn "restore_context_from_passport: anchor not found (skip; persist/send still protected)"
    }
  } else {
    Write-Info "restore_context_from_passport already normalized"
  }

  # 6) send_smart_split normalize outgoing (best-effort)
  if ($src -notmatch '(?m)^\s*text\s*=\s*_normalize_text\(text\)\s*$') {
    $src2 = Replace-First $src '(?m)^async def send_smart_split\(\s*update:\s*Update\s*,\s*text:\s*str\s*\)\s*->\s*None\s*:\s*$' `
      ("async def send_smart_split(update: Update, text: str) -> None:" + $nl +
       "    text = _normalize_text(text)")
    if ($src2 -ne $null) {
      $src = $src2
      Write-Ok "send_smart_split: normalize outgoing"
    } else {
      Write-Warn "send_smart_split: anchor not found (skip)"
    }
  } else {
    Write-Info "send_smart_split already normalized"
  }

  # 7) write back
  Write-Utf8NoBom $run $src
  Write-Ok "Patched: $run (UTF-8 no BOM write)"

  # smoke: py_compile
  Write-Info "smoke: py_compile"
  & $py -m py_compile $run | Out-Null
  Write-Ok "smoke: run_ester_fixed.py parses"

  # 8) optional sanitize passport JSONL
  if ($SanitizePassport) {
    $passport = Join-Path $proj "data\passport\clean_memory.jsonl"
    if (!(Test-Path $passport)) {
      Write-Warn "Passport JSONL not found: $passport (skip sanitize)"
    } else {
      $san = Join-Path $proj "tools\patches\sanitize_passport_encoding_B7.py"
      $pycode = @"
import os, sys, json, unicodedata

def redecode_utf8(s: str, src_enc: str):
    try:
        return s.encode(src_enc).decode("utf-8")
    except Exception:
        return None

def looks_mojibake(s: str) -> bool:
    if not s: return False
    if "vЂ" in s or "vњ" in s or "â€" in s: return True
    if "Ð" in s or "Ñ" in s: return True
    n = len(s)
    if n >= 20:
        rs = (s.count("R") + s.count("S")) / float(n)
        if rs > 0.18: return True
    return False

def score(s: str) -> int:
    if not s: return -10**9
    cyr = latin1 = bad = 0
    for ch in s:
        o = ord(ch)
        if 0x0400 <= o <= 0x04FF: cyr += 1
        elif 0x00A0 <= o <= 0x00FF: latin1 += 1
        elif ch == "\ufffd": bad += 5
    if "vЂ" in s: bad += 20
    if "vњ" in s: bad += 20
    if "â€" in s: bad += 20
    if "Ð" in s or "Ñ" in s: bad += 20
    return (cyr * 3) - (latin1 * 2) - (bad * 5)

def norm_text(x):
    if x is None: return x
    if isinstance(x, bytes):
        for enc in ("utf-8", "cp1251", "latin1", "cp1252", "cp866"):
            try:
                x = x.decode(enc); break
            except Exception:
                pass
        if isinstance(x, bytes):
            x = x.decode("utf-8", errors="replace")
    if not isinstance(x, str): return x
    s = unicodedata.normalize("NFC", x)
    if not looks_mojibake(s): return s
    best = s; best_sc = score(best)
    for enc in ("cp1251", "latin1", "cp1252", "cp866"):
        cand = redecode_utf8(s, enc)
        if cand is None: continue
        cand = unicodedata.normalize("NFC", cand)
        sc = score(cand)
        if sc > best_sc:
            best, best_sc = cand, sc
    return best

def norm_obj(obj):
    if obj is None: return obj
    if isinstance(obj, (str, bytes)): return norm_text(obj)
    if isinstance(obj, list): return [norm_obj(v) for v in obj]
    if isinstance(obj, tuple): return tuple(norm_obj(v) for v in obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            nk = norm_text(k) if isinstance(k, (str, bytes)) else k
            out[nk] = norm_obj(v)
        return out
    return obj

def main(path):
    with open(path, "rb") as f:
        raw_lines = f.read().splitlines()

    total = len(raw_lines)
    changed = 0
    bad_json = 0
    out_lines = []

    for b in raw_lines:
        s = b.decode("utf-8", errors="replace")
        try:
            rec = json.loads(s)
        except Exception:
            bad_json += 1
            out_lines.append(s)
            continue

        rec2 = norm_obj(rec)
        s2 = json.dumps(rec2, ensure_ascii=False)
        if s2 != s:
            changed += 1
        out_lines.append(s2)

    bak = path + ".bak_encoding"
    if not os.path.exists(bak):
        os.replace(path, bak)

    with open(path, "w", encoding="utf-8", newline="\\n") as f:
        for line in out_lines:
            f.write(line + "\\n")

    print(f"[sanitize] total={total} changed={changed} bad_json={bad_json}")
    print(f"[sanitize] backup={bak}")
    print(f"[sanitize] out={path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: sanitize_passport_encoding_B7.py <clean_memory.jsonl>")
        sys.exit(2)
    main(sys.argv[1])
"@
      $utf8 = New-Object System.Text.UTF8Encoding($false)
      [System.IO.File]::WriteAllText($san, $pycode, $utf8)
      Write-Ok "Wrote sanitizer: $san"
      Write-Info "Sanitize passport: $passport"
      & $py $san $passport
      Write-Ok "Passport sanitize done"
    }
  }

  Write-Ok "B7c applied successfully."
}
catch {
  Write-Err ("Patch failed: " + $_.Exception.Message)
  Write-Info "Rollback -> restore backup"
  Copy-Item $bak $run -Force
  Write-Ok "Restored: $run"
  throw
}
