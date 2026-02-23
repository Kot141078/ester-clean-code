# PowerShell 5.x — Apply patch: TG lock + no-autostart + chat_api fallback
# Run from D:\ester-project (project root)
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\apply_patch_20251226_tg_lock_context.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8NoBom([string]$Path, [string]$Content) {
  $enc = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $enc)
}

function Backup-File([string]$FilePath, [string]$BackupDir) {
  if (!(Test-Path -LiteralPath $FilePath)) {
    throw "Fayl ne nayden: $FilePath"
  }
  New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
  Copy-Item -LiteralPath $FilePath -Destination (Join-Path $BackupDir (Split-Path $FilePath -Leaf)) -Force
}

$PatchId = "20251226_tg_lock_context"
$Root = (Get-Location).Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupDir = Join-Path $Root (".patch_backups\" + $PatchId + "\" + $Stamp)

Write-Host ">>> PatchId=$PatchId" -ForegroundColor Cyan
Write-Host ">>> BackupDir=$BackupDir" -ForegroundColor Cyan

# --- 1) Replace small files polnostyu ---
$Target_TgAdapter = Join-Path $Root "messaging\telegram_adapter.py"
$Target_TgClient  = Join-Path $Root "modules\telegram_client.py"

Backup-File $Target_TgAdapter $BackupDir
Backup-File $Target_TgClient  $BackupDir

# NOTE: content blocks are appended at end of this script
Write-Utf8NoBom $Target_TgAdapter $Global:PATCH_TG_ADAPTER
Write-Utf8NoBom $Target_TgClient  $Global:PATCH_TG_CLIENT

# --- 2) Patch run_ester_fixed.py (insert lock helpers + gate before polling) ---
$Target_Run = Join-Path $Root "run_ester_fixed.py"
Backup-File $Target_Run $BackupDir
$runTxt = Get-Content -LiteralPath $Target_Run -Raw -Encoding UTF8

if ($runTxt -notmatch "Telegram getUpdates EXCLUSIVE LOCK") {
  $lockBlock = $Global:PATCH_RUN_LOCK_BLOCK
  # insert after TELEGRAM_TOKEN = ... line
  $runTxt2 = [regex]::Replace(
    $runTxt,
    "(?m)^(TELEGRAM_TOKEN\s*=.*\r?\n)",
    '$1' + "`r`n" + $lockBlock + "`r`n",
    1
  )
  if ($runTxt2 -eq $runTxt) { throw "Ne udalos vstavit lock-blok: TELEGRAM_TOKEN=... ne nayden." }
  $runTxt = $runTxt2
} else {
  Write-Host ">>> run_ester_fixed.py: lock-blok uzhe est — propuskayu vstavku." -ForegroundColor Yellow
}

# insert gate before ApplicationBuilder line
if ($runTxt -notmatch "TG lock: zapret dvoynogo getUpdates") {
  $gateBlock = $Global:PATCH_RUN_GATE_BLOCK
  $runTxt2 = [regex]::Replace(
    $runTxt,
    "(?m)^(    app\s*=\s*ApplicationBuilder\(\)\.token\(TELEGRAM_TOKEN\)\.build\(\)\s*\r?\n)",
    $gateBlock + "`r`n" + '$1',
    1
  )
  if ($runTxt2 -eq $runTxt) { throw "Ne udalos vstavit gate-blok: stroka ApplicationBuilder().token(TELEGRAM_TOKEN) ne naydena." }
  $runTxt = $runTxt2
} else {
  Write-Host ">>> run_ester_fixed.py: gate-blok uzhe est — propuskayu vstavku." -ForegroundColor Yellow
}

Write-Utf8NoBom $Target_Run $runTxt

# --- 3) Patch modules/chat_api.py (fallback pri peregruze konteksta) ---
$Target_ChatApi = Join-Path $Root "modules\chat_api.py"
if (Test-Path -LiteralPath $Target_ChatApi) {
  Backup-File $Target_ChatApi $BackupDir
  $chatTxt = Get-Content -LiteralPath $Target_ChatApi -Raw -Encoding UTF8

  if ($chatTxt -notmatch "def _smart_truncate") {
    $chatTxt = $chatTxt + "`r`n`r`n" + $Global:PATCH_CHATAPI_HELPER + "`r`n"
  }

  # Replace the legacy overload one-liner if present
  # (double-quoted so we can include both " and ' inside the character class)
  $pattern = "(?s)if\s+not\s+answer\s*:\s*\r?\n\s*answer\s*=\s*[\"\"']Izvini,\s*proizoshla\s*peregruzka\s*konteksta\.\s*Povtori\s*vopros\.\s*[\"\"']\s*\r?\n"
  if ([regex]::IsMatch($chatTxt, $pattern)) {
    $chatTxt = [regex]::Replace($chatTxt, $pattern, $Global:PATCH_CHATAPI_REPLACEMENT, 1)
    Write-Host ">>> chat_api.py: zamenil staruyu zaglushku peregruza konteksta." -ForegroundColor Green
  } else {
    Write-Host ">>> chat_api.py: shablon zaglushki ne nayden — fayl mog byt drugoy versii. Ya dobavil helper _smart_truncate (esli ego ne bylo)." -ForegroundColor Yellow
  }

  Write-Utf8NoBom $Target_ChatApi $chatTxt
} else {
  Write-Host ">>> modules/chat_api.py ne nayden — propuskayu." -ForegroundColor Yellow
}

Write-Host ">>> DONE. Backup: $BackupDir" -ForegroundColor Cyan
Write-Host ">>> Rollback: powershell -ExecutionPolicy Bypass -File .\rollback_patch_20251226_tg_lock_context.ps1 -BackupDir `"$BackupDir`"" -ForegroundColor Cyan

$Global:PATCH_TG_ADAPTER = @'
# -*- coding: utf-8 -*-
"""
messaging/telegram_adapter.py — Telegram inbox adapter (bezopasno dlya importa).

YaVNYY MOST: c=a+b — odin «kanal» Telegram (polling) + mnozhestvo moduley (routes/hooks) bez konkurentsii.
SKRYTYE MOSTY:
  - Ashby: requisite variety — raznye interfeysy (TG/HTTP) bez vzaimnykh pomekh.
  - Cover&Thomas: ogranichenie kanala — lock-fayl kak arbitr dostupa k getUpdates.
ZEMNOY ABZATs: dva protsessa, tyanuschie getUpdates odnovremenno, kak dva gruzchika za odin yaschik: yaschik padaet.
Lock nuzhen, chtoby byl odin «rul».
"""

import os
import time
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

import requests


# ---------------------------
# Helpers
# ---------------------------

def _env_flag(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _safe_int(v: str, default: int) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default


def _project_root() -> Path:
    # messaging/telegram_adapter.py -> project root
    return Path(__file__).resolve().parents[1]


def _default_lock_path() -> Path:
    return _project_root() / "data" / "locks" / "telegram_getupdates.lock"


def _try_acquire_lock(lock_path: Path):
    """
    Best-effort cross-process lock.
    Works on Windows (msvcrt) and Posix (fcntl).
    Returns an open file handle if lock acquired, else None.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path.as_posix(), "a+")
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # type: ignore
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.seek(0)
        f.truncate(0)
        f.write(f"pid={os.getpid()}\n")
        f.flush()
        return f
    except Exception:
        try:
            f.close()
        except Exception:
            pass
        return None


def _release_lock(lock_handle):
    if not lock_handle:
        return
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl  # type: ignore
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        lock_handle.close()
    except Exception:
        pass


# ---------------------------
# Config
# ---------------------------

@dataclass
class TgAdapterCfg:
    token: str
    poll_interval_sec: float = 1.0
    timeout_sec: int = 40
    inbox_path: Path = Path("data/inbox/telegram.jsonl")
    lock_path: Path = _default_lock_path()
    user_map_path: Path = Path("data/telegram_users.json")


def _read_env_cfg() -> TgAdapterCfg:
    TG_TOKEN = (
        os.getenv("TELEGRAM_TOKEN", "").strip()
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("TG_BOT_TOKEN", "").strip()
        or os.getenv("TG_TOKEN", "").strip()
    )
    poll_interval = float(os.getenv("ESTER_TG_ADAPTER_POLL_INTERVAL", "1.0").strip() or "1.0")
    timeout_sec = _safe_int(os.getenv("ESTER_TG_ADAPTER_TIMEOUT", "40"), 40)

    inbox_path = Path(os.getenv("ESTER_TG_ADAPTER_INBOX_PATH", "data/inbox/telegram.jsonl")).resolve()
    lock_path = Path(os.getenv("ESTER_TELEGRAM_LOCK_PATH", "") or str(_default_lock_path())).resolve()
    user_map_path = Path(os.getenv("ESTER_TG_ADAPTER_USERMAP", "data/telegram_users.json")).resolve()

    return TgAdapterCfg(
        token=TG_TOKEN,
        poll_interval_sec=poll_interval,
        timeout_sec=timeout_sec,
        inbox_path=inbox_path,
        lock_path=lock_path,
        user_map_path=user_map_path,
    )


CFG = _read_env_cfg()

# Esli u tebya osnovnoy Telegram-polling v run_ester_fixed.py — derzhi avtozapusk adaptera vyklyuchennym (po umolchaniyu on OFF).
ADAPTER_AUTOSTART = (
    _env_flag("ESTER_TG_ADAPTER_AUTOSTART", "0")
    or _env_flag("ESTER_TELEGRAM_ADAPTER_AUTOSTART", "0")
    or _env_flag("ESTER_TELEGRAM_AUTOSTART", "0")
)

ADAPTER_POLLING_DISABLED = (
    _env_flag("ESTER_TG_ADAPTER_POLLING_DISABLED", "0")
    or _env_flag("ESTER_TELEGRAM_POLLING_DISABLED", "0")
)


# ---------------------------
# Telegram Adapter
# ---------------------------

class TelegramAdapter:
    """
    Lightweight Telegram getUpdates poller that writes incoming messages into a jsonl inbox.

    IMPORTANT:
      - must not autostart by default (safe import),
      - must respect cross-process lock to avoid 409 Conflict.
    """

    def __init__(self, cfg: Optional[TgAdapterCfg] = None, on_message: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.cfg = cfg or CFG
        self._on_message = on_message
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock_handle = None
        self._offset = 0

    def start(self) -> bool:
        if not self.cfg.token:
            print("[TG-ADAPTER] No token (TELEGRAM_TOKEN/TELEGRAM_BOT_TOKEN/TG_BOT_TOKEN/TG_TOKEN) — not starting.")
            return False

        if ADAPTER_POLLING_DISABLED:
            print("[TG-ADAPTER] Polling disabled by env flag — not starting.")
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._lock_handle = _try_acquire_lock(self.cfg.lock_path)
        if not self._lock_handle:
            print(f"[TG-ADAPTER] Lock busy — another process polls getUpdates: {self.cfg.lock_path}")
            return False

        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._loop, name="TelegramAdapterPoller", daemon=True)
        self._thread.start()
        print("[TG-ADAPTER] Started.")
        return True

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        _release_lock(self._lock_handle)
        self._lock_handle = None
        print("[TG-ADAPTER] Stopped.")

    def _ensure_inbox_dir(self) -> None:
        self.cfg.inbox_path.parent.mkdir(parents=True, exist_ok=True)

    def _append_inbox(self, item: Dict[str, Any]) -> None:
        self._ensure_inbox_dir()
        with open(self.cfg.inbox_path.as_posix(), "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _tg_get_updates(self) -> List[Dict[str, Any]]:
        url = f"https://api.telegram.org/bot{self.cfg.token}/getUpdates"
        params = {
            "timeout": self.cfg.timeout_sec,
            "offset": self._offset,
            "allowed_updates": ["message"],
        }
        r = requests.get(url, params=params, timeout=self.cfg.timeout_sec + 5)
        if r.status_code == 409:
            print("[TG-ADAPTER] Conflict 409 — drugoy poller. Ostanavlivayus.")
            self._stop_evt.set()
            return []
        if r.status_code != 200:
            raise RuntimeError(f"Telegram HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data.get("result", [])

    def _loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                updates = self._tg_get_updates()
                for upd in updates:
                    uid = upd.get("update_id", 0)
                    if uid:
                        self._offset = max(self._offset, uid + 1)

                    msg = upd.get("message") or {}
                    if not msg:
                        continue

                    item = {
                        "ts": time.time(),
                        "source": "telegram",
                        "update_id": uid,
                        "chat_id": (msg.get("chat") or {}).get("id"),
                        "from": msg.get("from"),
                        "text": msg.get("text") or msg.get("caption") or "",
                        "raw": upd,
                    }
                    self._append_inbox(item)
                    if self._on_message:
                        try:
                            self._on_message(item)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[TG-ADAPTER] Loop error: {e}")
                time.sleep(2.0)

            time.sleep(self.cfg.poll_interval_sec)


# ---------------------------
# Module-level default adapter
# ---------------------------

_DEFAULT_ADAPTER: Optional[TelegramAdapter] = None


def get_default_adapter() -> TelegramAdapter:
    global _DEFAULT_ADAPTER
    if _DEFAULT_ADAPTER is None:
        _DEFAULT_ADAPTER = TelegramAdapter()
    return _DEFAULT_ADAPTER


# ---------------------------
# Optional autostart (OFF by default)
# ---------------------------

if ADAPTER_AUTOSTART and not ADAPTER_POLLING_DISABLED:
    try:
        get_default_adapter().start()
    except Exception as _e:
        print(f"[TG-ADAPTER] Autostart failed: {_e}")
'@
$Global:PATCH_TG_CLIENT = @'
# -*- coding: utf-8 -*-
"""
modules/telegram_client.py — prostoy Telegram long-poll (getUpdates) dlya zagruzki soobscheniy v inbox.

YaVNYY MOST: c=a+b — Telegram daet potok a (chelovek), obrabotka/pamyat dayut b (protsedury).
SKRYTYE MOSTY:
  - Ashby: requisite variety — TG/HTTP interfeysy, no bez konkurentsii za odin kanal.
  - Cover&Thomas: ogranichenie kanala — lock-fayl ogranichivaet odnovremennyy getUpdates.
ZEMNOY ABZATs: 409 Conflict — eto kak dva nasosa na odnu trubu: davlenie skachet, potok rvetsya.
"""

import os
import json
import time
import requests


def _env_flag(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _project_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _default_lock_path() -> str:
    return os.path.join(_project_root(), "data", "locks", "telegram_getupdates.lock")


def _try_acquire_lock(lock_path: str):
    """Best-effort cross-process lock for Telegram getUpdates."""
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    f = open(lock_path, "a+")
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # type: ignore
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.seek(0)
        f.truncate(0)
        f.write(f"pid={os.getpid()}\n")
        f.flush()
        return f
    except Exception:
        try:
            f.close()
        except Exception:
            pass
        return None


INBOX_PATH = os.getenv("ESTER_TG_INBOX_PATH", "data/inbox/telegram.jsonl")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or os.getenv("TG_TOKEN")


def ensure_inbox_dir():
    os.makedirs(os.path.dirname(INBOX_PATH), exist_ok=True)


def append_inbox(obj: dict):
    ensure_inbox_dir()
    with open(INBOX_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def listen():
    """Glavnyy tsikl long-poll. Pishet vkhodyaschie soobscheniya v jsonl."""
    # --- SAFETY GATES ---
    if not _env_flag("ESTER_TELEGRAM_ENABLED", "1"):
        print("[TG] Telegram client otklyuchen: ESTER_TELEGRAM_ENABLED=0")
        return
    if _env_flag("ESTER_TELEGRAM_POLLING_DISABLED", "0") or _env_flag("ESTER_TG_ADAPTER_POLLING_DISABLED", "0"):
        print("[TG] Polling otklyuchen flagom: ESTER_TELEGRAM_POLLING_DISABLED/ESTER_TG_ADAPTER_POLLING_DISABLED")
        return
    lock_path = os.getenv("ESTER_TELEGRAM_LOCK_PATH", "").strip() or _default_lock_path()
    lock_handle = _try_acquire_lock(lock_path)
    if not lock_handle:
        print(f"[TG] Propuskayu zapusk: drugoy protsess uzhe derzhit lock dlya getUpdates ({lock_path}).")
        return

    if not TG_TOKEN:
        print("[TG] ❌ OShIBKA: Ne zadan token (TELEGRAM_TOKEN/TELEGRAM_BOT_TOKEN/TG_BOT_TOKEN/TG_TOKEN) v .env")
        return

    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?timeout=30&offset={offset}"
            r = requests.get(url, timeout=40)
            if r.status_code == 409:
                print("[TG] Conflict 409: drugoy protsess uzhe delaet getUpdates. Ostanavlivayus.")
                try:
                    lock_handle.close()
                except Exception:
                    pass
                return

            if r.status_code != 200:
                print("[TG] Bad HTTP:", r.status_code, r.text[:200])
                time.sleep(2)
                continue

            data = r.json()
            if not data.get("ok"):
                print("[TG] Telegram API error:", data)
                time.sleep(2)
                continue

            updates = data.get("result", [])
            for upd in updates:
                offset = max(offset, upd.get("update_id", 0) + 1)
                msg = upd.get("message") or {}
                if not msg:
                    continue

                item = {
                    "ts": time.time(),
                    "source": "telegram",
                    "update_id": upd.get("update_id"),
                    "chat_id": (msg.get("chat") or {}).get("id"),
                    "from": msg.get("from"),
                    "text": msg.get("text") or msg.get("caption") or "",
                    "raw": upd,
                }
                append_inbox(item)

        except requests.exceptions.ReadTimeout:
            continue  # Taymaut seti — normalno dlya long-poll
        except Exception as e:
            print("[TG] Loop error:", e)
            time.sleep(2)


if __name__ == "__main__":
    listen()
'@
$Global:PATCH_RUN_LOCK_BLOCK = @'

# --- Telegram getUpdates EXCLUSIVE LOCK (zaschita ot dvoynogo pollinga) ---
# YaVNYY MOST: odin «kanal» Telegram -> odin poller; ostalnoe obschenie (HTTP/moduli) ne konfliktuet.
# SKRYTYE MOSTY: Ashby (raznoobrazie interfeysov bez pomekh), Cover&Thomas (lock kak ogranichenie kanala).
# ZEMNOY ABZATs: 409 Conflict — eto dva getUpdates odnovremenno; lock-fayl delaet odin shlang — odin nasos.

def _env_flag(name: str, default: str = "0") -> bool:
    v = os.getenv(name, default)
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

ESTER_TELEGRAM_ENABLED = _env_flag("ESTER_TELEGRAM_ENABLED", "1")

def _project_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))

DEFAULT_TELEGRAM_LOCK_PATH = os.path.join(_project_root(), "data", "locks", "telegram_getupdates.lock")
TELEGRAM_LOCK_PATH = (os.getenv("ESTER_TELEGRAM_LOCK_PATH", "").strip() or DEFAULT_TELEGRAM_LOCK_PATH)

_TG_LOCK_HANDLE = None

def _try_acquire_lock(lock_path: str):
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    f = open(lock_path, "a+")
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl  # type: ignore
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.seek(0)
        f.truncate(0)
        f.write(f"pid={os.getpid()}\n")
        f.flush()
        return f
    except Exception:
        try:
            f.close()
        except Exception:
            pass
        return None

def _release_lock(lock_handle):
    if not lock_handle:
        return
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl  # type: ignore
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        lock_handle.close()
    except Exception:
        pass

def _acquire_telegram_lock_or_none():
    global _TG_LOCK_HANDLE
    if _TG_LOCK_HANDLE:
        return _TG_LOCK_HANDLE
    h = _try_acquire_lock(TELEGRAM_LOCK_PATH)
    if not h:
        return None
    _TG_LOCK_HANDLE = h
    try:
        import atexit
        atexit.register(_release_lock, _TG_LOCK_HANDLE)
    except Exception:
        pass
    return _TG_LOCK_HANDLE

'@
$Global:PATCH_RUN_GATE_BLOCK = @'
    # --- TG lock: zapret dvoynogo getUpdates ---
    if not ESTER_TELEGRAM_ENABLED:
        print("[TG] Telegram otklyuchen: ESTER_TELEGRAM_ENABLED=0")
        return
    lock_h = _acquire_telegram_lock_or_none()
    if not lock_h:
        print(f"[TG] LOCK zanyat (drugoy protsess uzhe delaet getUpdates): {TELEGRAM_LOCK_PATH}")
        print("[TG] Ostanovi drugoy Telegram-poller ili vyklyuchi ego (ESTER_TG_ADAPTER_AUTOSTART=0 / ESTER_TELEGRAM_ENABLED=0).")
        return

'@
$Global:PATCH_CHATAPI_HELPER = @'
def _smart_truncate(text: str, limit_chars: int = 40000) -> str:
    # Safe truncation for oversized system prompts.
    # Keeps head+tail so that "policy" (head) and "recent context" (tail) survive.
    if text is None:
        return ""
    s = str(text)
    if limit_chars <= 0 or len(s) <= limit_chars:
        return s
    half = max(2000, limit_chars // 2)
    head = s[:half]
    tail = s[-half:]
    return head + "\n\n[...TRUNCATED FOR CONTEXT BUDGET...]\n\n" + tail

'@
$Global:PATCH_CHATAPI_REPLACEMENT = @'
if not answer:
        # A/B fallback: esli pokhozhe na perepolnenie konteksta/resursov — probuem odin povtor s ukorochennym system_prompt.
        err_l = (str(err) if err else "").lower()
        if ("context" in err_l) or ("token" in err_l) or ("prompt" in err_l) or ("too long" in err_l) or ("maximum" in err_l) or ("oom" in err_l) or ("out of memory" in err_l) or ("cuda" in err_l):
            try:
                limit = int(os.getenv("ESTER_SAFE_PROMPT_CHARS", "40000"))
            except Exception:
                limit = 40000
            try:
                sp2 = _smart_truncate(system_prompt, limit_chars=limit)
                answer2, usage2, err2 = _call_llm(user_text, sp2)
                if answer2:
                    answer = answer2
                    usage = usage2
                    err = err2 or err
            except Exception as _e2:
                err = err or str(_e2)

        if not answer:
            answer = "Izvini, seychas uperlis v limit konteksta/resursov. Skazhi to zhe samoe koroche (1–2 fakta) — prodolzhim."

'@
