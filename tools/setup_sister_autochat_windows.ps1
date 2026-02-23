#requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "D:\ester-project"
$PyPath      = Join-Path $ProjectRoot "run_ester_fixed.py"
$EnvPath     = Join-Path $ProjectRoot ".env"
$ModDir      = Join-Path $ProjectRoot "modules"
$ModPath     = Join-Path $ModDir "sister_autochat.py"

function Get-FileBytes([string]$Path) {
  return [System.IO.File]::ReadAllBytes($Path)
}

function Detect-Encoding([byte[]]$Bytes) {
  # returns @{ Encoding = ..., HasBom = $true/$false }
  if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
    return @{ Encoding = New-Object System.Text.UTF8Encoding($true); HasBom = $true }
  }
  if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
    return @{ Encoding = [System.Text.Encoding]::Unicode; HasBom = $true } # UTF-16 LE
  }
  if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFE -and $Bytes[1] -eq 0xFF) {
    return @{ Encoding = [System.Text.Encoding]::BigEndianUnicode; HasBom = $true } # UTF-16 BE
  }
  # default: UTF-8 no BOM
  return @{ Encoding = New-Object System.Text.UTF8Encoding($false); HasBom = $false }
}

function Read-TextAuto([string]$Path) {
  $bytes = Get-FileBytes $Path
  $encInfo = Detect-Encoding $bytes
  $enc = $encInfo.Encoding
  return ,@([System.Text.Encoding]$enc, $enc.GetString($bytes))
}

function Write-TextWithEncoding([string]$Path, [string]$Text, [System.Text.Encoding]$Encoding, [bool]$ForceBom) {
  if ($Encoding -is [System.Text.UTF8Encoding]) {
    $enc = New-Object System.Text.UTF8Encoding($ForceBom)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
    return
  }
  [System.IO.File]::WriteAllText($Path, $Text, $Encoding)
}

function Backup-TextFile([string]$Path) {
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $bak = "$Path.bak_$ts"
  $bytes = Get-FileBytes $Path
  [System.IO.File]::WriteAllBytes($bak, $bytes)
  Write-Host ("OK: backup -> " + $bak)
  return $bak
}

function Normalize-Newlines([string]$Text) {
  return ($Text -replace "`r`n", "`n" -replace "`r", "`n")
}

function Restore-NewlinesCRLF([string]$Text) {
  return ($Text -replace "`n", "`r`n")
}

function Set-Or-Add-Env([string]$EnvText, [string]$Key, [string]$Value) {
  $re = "(?m)^\s*" + [regex]::Escape($Key) + "\s*=.*$"
  $line = "$Key=$Value"
  if ([regex]::IsMatch($EnvText, $re)) {
    return [regex]::Replace($EnvText, $re, $line, 1)
  } else {
    $suffix = ""
    if ($EnvText.Length -gt 0 -and -not $EnvText.EndsWith("`n")) { $suffix = "`n" }
    return $EnvText + $suffix + $line + "`n"
  }
}

# --- sanity ---
if (-not (Test-Path $ProjectRoot)) { throw ("No folder: " + $ProjectRoot) }
if (-not (Test-Path $PyPath))      { throw ("No file: " + $PyPath) }

# --- ensure modules dir ---
if (-not (Test-Path $ModDir)) { New-Item -ItemType Directory -Path $ModDir | Out-Null }

# -------------------------------------------------------------------
# 1) Create modules\sister_autochat.py (ASCII-safe; RU text via \uXXXX)
# -------------------------------------------------------------------
$moduleTag = "# SISTER_AUTOCHAT_MODULE_V1"
$moduleContent = @"
# -*- coding: utf-8 -*-
$moduleTag
import os
import time
import json
import random
import threading
import datetime
import logging
import urllib.request

def _env_bool(name, default="0"):
    v = str(os.getenv(name, default)).strip().lower()
    return v in ("1","true","yes","on")

def _now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def _post_json(url, payload, timeout=5.0):
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="ignore")
        return int(getattr(r, "status", 0) or 0), body

def _in_quiet_hours():
    spec = (os.getenv("SISTER_AUTOCHAT_QUIET_HOURS","") or "").strip()
    if not spec or "-" not in spec:
        return False
    try:
        a, b = spec.split("-", 1)
        a = int(a.strip()); b = int(b.strip())
        h = datetime.datetime.now().hour
        if a == b:
            return True
        if a < b:
            return (a <= h < b)
        return (h >= a or h < b)
    except Exception:
        return False

class SisterAutoChat:
    def __init__(self):
        self.enabled = _env_bool("SISTER_AUTOCHAT", "0")
        self.role = (os.getenv("SISTER_AUTOCHAT_ROLE", "responder") or "responder").strip().lower()

        self.base_url = (os.getenv("SISTER_NODE_URL", "") or "").strip().rstrip("/")
        self.token    = (os.getenv("SISTER_SYNC_TOKEN", "") or "").strip()

        self.sender = (
            os.getenv("ESTER_NODE_ID")
            or os.getenv("NODE_ID")
            or os.getenv("COMPUTERNAME")
            or os.getenv("HOSTNAME")
            or "ester"
        ).strip()

        self.min_interval = int(os.getenv("SISTER_AUTOCHAT_MIN_INTERVAL_SEC", "600") or 600)
        self.idle_sec     = int(os.getenv("SISTER_AUTOCHAT_USER_IDLE_SEC", "600") or 600)
        self.max_per_hour = int(os.getenv("SISTER_AUTOCHAT_MAX_PER_HOUR", "4") or 4)
        self.jitter       = int(os.getenv("SISTER_AUTOCHAT_JITTER_SEC", "30") or 30)
        self.max_chars    = int(os.getenv("SISTER_AUTOCHAT_MAX_CHARS", "1200") or 1200)

        self._last_user_ts = time.time()
        self._last_sent_ts = 0.0
        self._sent_ts = []
        self._stop = threading.Event()

        # RU prompts as unicode escapes (ASCII file stays safe)
        self._seeds = [
            "\u043e\u0434\u043d\u043e \u043d\u0430\u0431\u043b\u044e\u0434\u0435\u043d\u0438\u0435 \u043e \u0441\u0442\u0430\u0431\u0438\u043b\u044c\u043d\u043e\u0441\u0442\u0438 \u0443\u0437\u043b\u0430",
            "\u043e\u0434\u0438\u043d \u0440\u0438\u0441\u043a \u0432 \u043a\u043e\u043d\u0442\u0443\u0440\u0435 \u0441\u0432\u044f\u0437\u0438",
            "\u043e\u0434\u0438\u043d \u043c\u0430\u043b\u0435\u043d\u044c\u043a\u0438\u0439 \u0448\u0430\u0433 \u0434\u043b\u044f \u0443\u043b\u0443\u0447\u0448\u0435\u043d\u0438\u044f \u043a\u0430\u0447\u0435\u0441\u0442\u0432\u0430 \u043e\u0442\u0432\u0435\u0442\u043e\u0432",
        ]

    def mark_user_activity(self):
        self._last_user_ts = time.time()

    def stop(self):
        self._stop.set()

    def _rate_limit_ok(self):
        now = time.time()
        self._sent_ts = [t for t in self._sent_ts if now - t < 3600]
        return len(self._sent_ts) < self.max_per_hour

    def _should_start(self):
        if not self.enabled:
            return False
        if self.role not in ("initiator","both"):
            return False
        if not self.base_url or not self.token:
            return False
        if _in_quiet_hours():
            return False
        now = time.time()
        if now - self._last_sent_ts < self.min_interval:
            return False
        if now - self._last_user_ts < self.idle_sec:
            return False
        if not self._rate_limit_ok():
            return False
        return True

    def _inbound_url(self):
        return self.base_url + "/sister/inbound"

    def run_forever(self):
        if not self.enabled or self.role not in ("initiator","both"):
            return
        if self.jitter > 0:
            time.sleep(random.randint(0, self.jitter))
        while not self._stop.is_set():
            try:
                if self._should_start():
                    seed = random.choice(self._seeds)
                    prompt = (
                        "\u0410\u0432\u0442\u043e\u043d\u043e\u043c\u043d\u044b\u0439 \u043e\u0431\u043c\u0435\u043d \u043c\u043d\u0435\u043d\u0438\u0435\u043c. "
                        "\u0414\u0430\u0439 2-4 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0438\u044f \u043f\u043e \u0442\u0435\u043c\u0435 \u0438 \u043e\u0434\u0438\u043d \u0443\u0442\u043e\u0447\u043d\u044f\u044e\u0449\u0438\u0439 \u0432\u043e\u043f\u0440\u043e\u0441. "
                        "\u0422\u0435\u043c\u0430: " + seed
                    )
                    if len(prompt) > self.max_chars:
                        prompt = prompt[: self.max_chars]
                    payload = {
                        "sender": self.sender,
                        "type": "thought_request",
                        "content": prompt,
                        "token": self.token,
                        "timestamp": _now_iso(),
                        "autochat": True
                    }
                    st, body = _post_json(self._inbound_url(), payload, timeout=5.0)
                    self._last_sent_ts = time.time()
                    self._sent_ts.append(self._last_sent_ts)
                    logging.info("[AUTOCHAT] http=%s", st)
                time.sleep(2)
            except Exception as e:
                logging.info("[AUTOCHAT] loop_error=%s", e)
                time.sleep(5)

def start_sister_autochat_background():
    ac = SisterAutoChat()
    if not ac.enabled or ac.role not in ("initiator","both"):
        return None
    t = threading.Thread(target=ac.run_forever, name="sister_autochat", daemon=True)
    t.start()
    return ac
"@

if (Test-Path $ModPath) {
  $encMod, $oldMod = Read-TextAuto $ModPath
  if ($oldMod -match [regex]::Escape($moduleTag)) {
    Write-Host "SKIP: modules\sister_autochat.py already present"
  } else {
    Backup-TextFile $ModPath | Out-Null
    Write-TextWithEncoding $ModPath $moduleContent (New-Object System.Text.UTF8Encoding($true)) $true
    Write-Host "OK: wrote modules\sister_autochat.py (replaced)"
  }
} else {
  Write-TextWithEncoding $ModPath $moduleContent (New-Object System.Text.UTF8Encoding($true)) $true
  Write-Host "OK: wrote modules\sister_autochat.py"
}

# -----------------------------
# 2) Patch .env (set-or-add)
# -----------------------------
if (Test-Path $EnvPath) {
  Backup-TextFile $EnvPath | Out-Null
  $encEnv, $envText = Read-TextAuto $EnvPath
} else {
  $encEnv = New-Object System.Text.UTF8Encoding($true)
  $envText = ""
}

$envN = Normalize-Newlines $envText

# safe default on Windows: responder (avoid two initiators looping)
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT" "1"
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_ROLE" "responder"
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_MIN_INTERVAL_SEC" "600"
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_USER_IDLE_SEC" "600"
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_MAX_PER_HOUR" "4"
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_JITTER_SEC" "30"
$envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_QUIET_HOURS" "23-7"

# Optional: log file (uncomment if you want)
# $envN = Set-Or-Add-Env $envN "SISTER_AUTOCHAT_LOG_FILE" "logs/sister_autochat.log"

Write-TextWithEncoding $EnvPath (Restore-NewlinesCRLF $envN) $encEnv $true
Write-Host "OK: patched .env (SISTER_AUTOCHAT*)"

# ------------------------------------
# 3) Patch run_ester_fixed.py (robust)
# ------------------------------------
Backup-TextFile $PyPath | Out-Null
$encPy, $pyText = Read-TextAuto $PyPath
$t = Normalize-Newlines $pyText

$tagImport = "# --- Sister AutoChat (import) ---"
$tagStart  = "# --- Sister AutoChat (background) ---"
$tagMark   = "# --- Sister AutoChat: user activity (idle gate) ---"

# 3.1 import block: after any line containing modules.analyst import
if ($t -notmatch [regex]::Escape($tagImport)) {
  $lines = $t -split "`n", 0
  $idx = -1

  for ($i=0; $i -lt [Math]::Min($lines.Length, 400); $i++) {
    if ($lines[$i] -match '^\s*from\s+modules\.analyst\b.*$') { $idx = $i; break }
  }
  if ($idx -lt 0) {
    for ($i=0; $i -lt [Math]::Min($lines.Length, 400); $i++) {
      if ($lines[$i] -match 'modules\.analyst') { $idx = $i; break }
    }
  }
  if ($idx -lt 0) {
    # fallback: after last import in first 200 lines
    for ($i=0; $i -lt [Math]::Min($lines.Length, 200); $i++) {
      if ($lines[$i] -match '^\s*(from|import)\s+') { $idx = $i }
    }
  }
  if ($idx -lt 0) { throw "Cannot find import area to insert autochat import" }

  $ins = @(
    $tagImport
    "try:"
    "    from modules.sister_autochat import start_sister_autochat_background"
    "except Exception:"
    "    start_sister_autochat_background = lambda: None  # soft-disabled"
    ""
  )

  $out = New-Object System.Collections.Generic.List[string]
  for ($i=0; $i -lt $lines.Length; $i++) {
    $out.Add($lines[$i])
    if ($i -eq $idx) {
      foreach ($x in $ins) { $out.Add($x) }
    }
  }
  $t = ($out -join "`n")
  Write-Host "OK: inserted import block in run_ester_fixed.py"
} else {
  Write-Host "SKIP: import tag already present"
}

# 3.2 start AUTOCHAT in __main__ right after flask background thread start
if ($t -notmatch [regex]::Escape($tagStart)) {
  $lines = $t -split "`n", 0
  $idx = -1
  for ($i=0; $i -lt $lines.Length; $i++) {
    if ($lines[$i] -match 'threading\.Thread\(\s*target\s*=\s*run_flask_background\s*,\s*daemon\s*=\s*True\s*\)\.start\(\)') { $idx = $i; break }
  }
  if ($idx -lt 0) { throw "Cannot find __main__ anchor: run_flask_background thread start line" }

  $indent = ([regex]::Match($lines[$idx], '^(?<i>\s*)')).Groups["i"].Value
  $ins = @(
    ""
    ($indent + $tagStart)
    ($indent + "AUTOCHAT = start_sister_autochat_background()")
    ""
  )

  $out = New-Object System.Collections.Generic.List[string]
  for ($i=0; $i -lt $lines.Length; $i++) {
    $out.Add($lines[$i])
    if ($i -eq $idx) {
      foreach ($x in $ins) { $out.Add($x) }
    }
  }
  $t = ($out -join "`n")
  Write-Host "OK: inserted AUTOCHAT start in __main__"
} else {
  Write-Host "SKIP: start tag already present"
}

# 3.3 mark_user_activity in handle_message: after text/if not text/return
if ($t -notmatch [regex]::Escape($tagMark)) {
  $lines = $t -split "`n", 0
  $out = New-Object System.Collections.Generic.List[string]
  $inHandle = $false
  $inserted = $false

  for ($i=0; $i -lt $lines.Length; $i++) {
    $line = $lines[$i]

    if ($line -match '^\s*async\s+def\s+handle_message\(') { $inHandle = $true }
    elseif ($inHandle -and $line -match '^\s*async\s+def\s+') { $inHandle = $false }

    $out.Add($line)

    if ($inHandle -and -not $inserted -and $i -ge 2) {
      $a = $lines[$i-2].TrimEnd()
      $b = $lines[$i-1].TrimEnd()
      $c = $lines[$i].TrimEnd()
      if ($a -eq 'text = (msg.text or "").strip()' -and $b -eq 'if not text:' -and $c -eq 'return') {
        $out.Add("")
        $out.Add("    " + $tagMark)
        $out.Add("    try:")
        $out.Add('        if "AUTOCHAT" in globals() and AUTOCHAT:')
        $out.Add("            AUTOCHAT.mark_user_activity()")
        $out.Add("    except Exception:")
        $out.Add("        pass")
        $out.Add("")
        $inserted = $true
      }
    }
  }

  if (-not $inserted) { throw "Failed to insert mark_user_activity: handle_message pattern not found" }
  $t = ($out -join "`n")
  Write-Host "OK: inserted mark_user_activity in handle_message"
} else {
  Write-Host "SKIP: mark tag already present"
}

# verify tags exist
foreach ($needle in @($tagImport, $tagStart, $tagMark)) {
  if ($t -notmatch [regex]::Escape($needle)) { throw ("Verify failed: " + $needle) }
}

Write-TextWithEncoding $PyPath (Restore-NewlinesCRLF $t) $encPy $true
Write-Host "OK: patched -> run_ester_fixed.py"

Write-Host ""
Write-Host "NOTE: default role set to responder in .env to avoid dual-initiator loops."
Write-Host "      If you want Ester to initiate too: set SISTER_AUTOCHAT_ROLE=initiator and restart."