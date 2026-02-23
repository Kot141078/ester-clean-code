#requires -Version 5.1
<#
apply_patch_20251227_ctxq_v3.ps1
- Robust Regex-based patching to fix "Needle not found" error.
- Creates modules\context_question_engine.py
- Patches run_ester_fixed.py
#>

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function _WriteUtf8Bom([string]$Path, [string]$Text) {
    $enc = [System.Text.Encoding]::UTF8
    $bytes = [System.Text.Encoding]::UTF8.GetPreamble() + [System.Text.Encoding]::UTF8.GetBytes($Text)
    [System.IO.File]::WriteAllBytes($Path, $bytes)
}

$ProjectDir = (Get-Location).Path
$Runner = Join-Path $ProjectDir "run_ester_fixed.py"
$ModuleDir = Join-Path $ProjectDir "modules"
$Module = Join-Path $ModuleDir "context_question_engine.py"

Write-Host ">>> CTXQ Patch V3 (Robust Regex)" -ForegroundColor Cyan
Write-Host "Target: $Runner"

if (!(Test-Path $Runner)) { throw "run_ester_fixed.py not found!" }
if (!(Test-Path $ModuleDir)) { New-Item -ItemType Directory -Path $ModuleDir -Force | Out-Null }

# --- 1. CREATE MODULE (Python Code) ---
$CTXQ_MODULE_CODE = @'
# -*- coding: utf-8 -*-
"""
modules/context_question_engine.py — CTXQ: Kontekstnyy generator voprosov dlya Ester.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import re
import time
import os

_RU_MONTHS = {
    "yanvarya": 1, "fevralya": 2, "marta": 3, "aprelya": 4, "maya": 5, "iyunya": 6,
    "iyulya": 7, "avgusta": 8, "sentyabrya": 9, "oktyabrya": 10, "noyabrya": 11, "dekabrya": 12
}

@dataclass
class CtxqInput:
    now: datetime
    history: List[Dict[str, Any]]
    internal_state: Dict[str, Any]
    recalled: List[str]
    user_profile: Dict[str, Any]

@dataclass
class CtxqResult:
    question: str
    reason: str
    priority: int
    fingerprint: str

class ContextQuestionEngine:
    def __init__(self) -> None:
        self._last_ts: float = 0.0
        self._last_fp: str = ""
        self._cooldown_sec: float = 1800.0

    def set_cooldown(self, seconds: float) -> None:
        try:
            s = float(seconds)
            self._cooldown_sec = max(30.0, s)
        except Exception: pass

    def refine_or_replace(self, proposed: str, inp: CtxqInput, *, allow_replace: bool = True) -> Tuple[str, str]:
        proposed = self._normalize_question(proposed or "")
        best = self._generate_question(inp)
        q2, reason2, prio2 = best if best else (None, None, 0)

        if q2 and allow_replace and prio2 >= 90:
            return q2, f"ctxq_replace(high_priority): {reason2}"

        if (len(proposed) > 300) or self._looks_like_noise(proposed):
            if q2: return q2, f"ctxq_replace(noise_fix): {reason2}"
            return self._trim(proposed, 220), "ctxq_trim(proposed_long)"

        if q2 and allow_replace and prio2 >= 60 and self._time_bucket(inp.now) != "day":
            return q2, f"ctxq_replace(timefit): {reason2}"

        if proposed:
            return self._trim(proposed, 250), "ctxq_keep(proposed)"
        
        if q2: return q2, f"ctxq_fallback: {reason2}"
        return "Kak ty seychas?", "ctxq_fallback_default"

    def _generate_question(self, inp: CtxqInput) -> Optional[Tuple[str, str, int]]:
        now = inp.now
        bucket = self._time_bucket(now)
        
        # 1. Birthday
        bd = self._get_birthdate(inp)
        if bd:
            days = self._days_to_monthday(now, bd[0], bd[1])
            if days is not None:
                if days == 0: return ("Segodnya tvoy den rozhdeniya. Kak ty khochesh provesti etot den?", f"birthday_today", 100)
                if 0 < days <= 14: return (f"Skoro den rozhdeniya (cherez {days} dn.). Chego tebe khochetsya?", f"birthday_soon", 95)

        # 2. Urgent
        urgent = self._find_urgent_theme(inp.history)
        if urgent:
            return (f"Po teme «{urgent}»: kakoy status?", f"urgent({urgent})", 85)

        # 3. Topics
        topics = self._extract_topics(inp.history, inp.recalled)
        top = topics[0] if topics else ""

        if bucket == "morning":
            return (f"Dobroe utro. Chto segodnya glavnoe po «{top}»?" if top else "Dobroe utro. Kakie plany?", "morning", 70)
        if bucket == "day":
            return (f"Kak dela s «{top}»?" if top else "Kak idet den?", "day", 60)
        if bucket == "evening":
            return (f"Vecherniy chek: chto udalos po «{top}»?" if top else "Kak proshel den?", "evening", 65)
        
        return (f"Noch. Zakryvaem petlyu po «{top}»?" if top else "Noch. Otdykhaem?", "night", 55)

    def _time_bucket(self, now: datetime) -> str:
        h = int(now.hour)
        if 5 <= h < 11: return "morning"
        if 11 <= h < 17: return "day"
        if 17 <= h < 23: return "evening"
        return "night"

    def _normalize_question(self, s: str) -> str:
        s = re.sub(r"\s+", " ", (s or "").strip())
        s = re.sub(r"\s*—?\s*(podpis|signature|#Ester).*", "", s, flags=re.I)
        return s.strip()

    def _trim(self, s: str, n: int) -> str:
        if len(s) <= n: return s
        return s[:n].rstrip() + "…"

    def _looks_like_noise(self, s: str) -> bool:
        if not s: return True
        if len(re.findall(r"[/\]{2,}|\b[A-Z]:\\", s)) >= 1: return True
        return False

    def _get_birthdate(self, inp: CtxqInput) -> Optional[Tuple[int, int]]:
        raw = str((inp.user_profile or {}).get("birthdate") or "").strip()
        m = re.match(r"^(\d{1,2})[.\-/](\d{1,2})$", raw)
        if m: return (int(m.group(1)), int(m.group(2)))
        return None

    def _days_to_monthday(self, now: datetime, day: int, month: int) -> Optional[int]:
        try:
            target = datetime(now.year, month, day, 12, 0)
            delta = (target.date() - now.date()).days
            if delta < -300: delta = (datetime(now.year + 1, month, day).date() - now.date()).days
            return int(delta)
        except: return None

    def _find_urgent_theme(self, history: List[Dict]) -> str:
        text = " ".join([str(x.get("text", "")) for x in history[-25:]])
        if re.search(r"\b(srochno|dedlayn|urgent|fail|error)\b", text, flags=re.I):
            return "Srochnoe"
        return ""

    def _extract_topics(self, history: List[Dict], recalled: List[str]) -> List[str]:
        # Simple stub
        return ["Tekuschee"]
'@
_WriteUtf8Bom -Path $Module -Text $CTXQ_MODULE_CODE
Write-Host "Module written." -ForegroundColor Green


# --- 2. PATCH RUNNER (REGEX) ---
$src = Get-Content -Path $Runner -Raw -Encoding UTF8
$modified = $false

# A. Insert Import Block
if ($src -notmatch "modules\.context_question_engine") {
    Write-Host "Injecting Import block..." -ForegroundColor Cyan
    $CTXQ_IMPORT_BLOCK = @'
# --- 6b) CTXQ (Context Question Engine) ---
CTXQ_AVAILABLE = False
CTXQ_ENGINE = None
try:
    from modules.context_question_engine import ContextQuestionEngine, CtxqInput
    CTXQ_ENGINE = ContextQuestionEngine()
    try:
        CTXQ_ENGINE.set_cooldown(float(os.getenv("ESTER_CTXQ_MIN_INTERVAL_SEC", "1800") or "1800"))
    except Exception: pass
    CTXQ_AVAILABLE = True
except Exception:
    CTXQ_AVAILABLE = False
    CTXQ_ENGINE = None
'@
    # Replace load_dotenv() with load_dotenv() + new code
    $src = $src -replace "load_dotenv\(\)", ("load_dotenv()`n" + $CTXQ_IMPORT_BLOCK)
    $modified = $true
}

# B. Replace SEND_MESSAGE logic (The part that failed previously)
# We use Regex to match the line regardless of indentation (whitespace) and specific ellipsis char
$needleRegex = "(?m)^(\s*)await context\.bot\.send_message\(chat_id=int\(ADMIN_ID\), text=f[`"']✨ Mysl prishla[.…]+ \{payload\}[`"']\)"

if ($src -match $needleRegex) {
    Write-Host "Found send_message line! Patching..." -ForegroundColor Cyan
    
    # Capture the indentation from the match ($matches[1]) to preserve python structure
    $indent = $matches[1]
    
    # Prepare replacement code with correct indentation
    $newLogic = @"
${indent}# CTXQ refine/replace
${indent}try:
${indent}    if CTXQ_ENGINE and str(os.getenv("ESTER_CTXQ_ENABLED", "1")).lower() not in ("0","false","off"):
${indent}        try:
${indent}            from zoneinfo import ZoneInfo
${indent}            _dt = datetime.datetime.fromtimestamp(_safe_now_ts(), tz=ZoneInfo("UTC"))
${indent}        except: _dt = datetime.datetime.now()
${indent}        _hist = []
${indent}        try: _hist = short_term_by_key(str(ADMIN_ID))[-80:]
${indent}        except: pass
${indent}        _inp = CtxqInput(now=_dt, history=_hist, internal_state={"node": NODE_IDENTITY}, recalled=[], user_profile={"birthdate": os.getenv("ESTER_USER_BIRTHDATE", "")})
${indent}        payload, _ = CTXQ_ENGINE.refine_or_replace(payload, _inp)
${indent}except Exception: pass
${indent}await context.bot.send_message(chat_id=int(ADMIN_ID), text=f"✨ Mysl prishla… {payload}")
"@
    
    # Perform regex replace
    $src = [regex]::Replace($src, $needleRegex, $newLogic)
    $modified = $true
} else {
    if ($src -match "CTXQ_ENGINE\.refine_or_replace") {
        Write-Host "Already patched." -ForegroundColor Gray
    } else {
        Write-Host "WARNING: Regex needle not found. Check file content manually." -ForegroundColor Red
        # Debug: print what we were looking for
        Write-Host "Regex was: $needleRegex"
    }
}

if ($modified) {
    $bak = "$Runner.bak_v3"
    Copy-Item -Path $Runner -Destination $bak -Force
    _WriteUtf8Bom -Path $Runner -Text $src
    
    Write-Host "Compiling to check syntax..."
    & python -m py_compile $Runner $Module
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PATCH COMPLETE & VERIFIED." -ForegroundColor Green
    } else {
        Write-Host "SYNTAX ERROR detected. Restoring backup..." -ForegroundColor Red
        Copy-Item -Path $bak -Destination $Runner -Force
    }
} else {
    Write-Host "No changes required." -ForegroundColor Green
}