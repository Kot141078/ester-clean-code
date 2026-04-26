# -*- coding: utf-8 -*-
"""run_ester_fixed.py — Telegram-uzel Ester (HiveMind + Volya/Sny/Lyubopytstvo)

YaVNYY MOST: c = a + b (chelovek + protsedury) -> ansambl mneniy + sintez + kaskad. SKRYTYE MOSTY:

Ashby: requisite variety - parallelnye provaydery dayut raznoobrazie, kaskad - stabilizatsiyu.

Cover&Thomas: ogranichenie kanala - sny lokalno (ekonomiya kanala/stoimosti), otvety - oblako.

Legacy Memory: Podklyuchenie starykh arkhivov (jsonl) kak "dolgosrochnoy pamyati" pri starte.

ZEMNOY ABZATs (inzheneriya/anatomiya): Planirovschik - kak sinusovyy uzel, zadaet ritm. A “son” — kak vosstanovlenie tkaney: on idet fonom i ne dolzhen blokirovat serdtsebienie (job tick), inache nachinayutsya “aritmii” (skipped jobs)."""

import base64
import os

# === IMPLANTS FOR CONNECTION (FLASK + REGUESC) ===
import threading
from flask import Flask, request, jsonify
import requests
from modules.telegram_runtime_helpers import document_delivery_failure_notice as _document_delivery_failure_notice
from modules.telegram_runtime_helpers import passport_record_to_short_term_messages as _passport_record_to_short_term_messages


# --- FATIGUE SYSTEM ---
CURRENT_FATIGUE = 0
FATIGUE_LIMIT = 200  # Fatigue threshold before forced sleep
FATIGUE_DEBUG = True


# --- WEB CONTEXT BRIDGE (ephemeral, per-chat) ---
WEB_CONTEXT_BY_CHAT = {}  # type: ignore
WEB_CONTEXT_TTL = 120  # sekund
# --- RECENT ACTIVITY CACHE (per-chat) ---
RECENT_ACTIVITY_CACHE_BY_CHAT = {}  # type: ignore
RECENT_DOC_BY_CHAT = {}  # type: ignore
RECENT_DOC_TTL_SEC = int(os.getenv("RECENT_DOC_TTL_SEC", "21600") or 21600)

import sys
import re
import json
import uuid
import time
import random
import asyncio
import logging
import warnings
import unicodedata
import threading
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from collections import Counter, deque
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import numpy as np
from dotenv import load_dotenv
# NOTE: Telegram handle_message is implemented in this file (do not import from modules.chat_api)
from modules.memory.journal import record_event
from modules.synaps import (
    SynapsMessageType as _SynapsMessageType,
    config_from_legacy_listener_values as _synaps_config_from_legacy_listener_values,
    handle_inbound_payload as _handle_synaps_inbound_payload,
)
from bridges.internet_access import internet
from modules.analyst import analyst
from skills.manager import SkillManager
from modules.register_all import register_all_skills
try:
    from modules.curiosity.unknown_detector import maybe_open_ticket as _curiosity_maybe_open_ticket  # type: ignore
except Exception:
    _curiosity_maybe_open_ticket = None  # type: ignore
try:
    from modules.memory.passport_indexer import index_record as _passport_index_record  # type: ignore
    from modules.memory.passport_indexer import import_passport as _passport_import_passport  # type: ignore
    from modules.memory.passport_indexer import rollup_passport_tail as _passport_rollup_tail  # type: ignore
except Exception:
    _passport_index_record = None
    _passport_import_passport = None
    _passport_rollup_tail = None
try:
    from modules.proactivity import token_cost_report as _token_cost_report  # type: ignore
except Exception:
    _token_cost_report = None  # type: ignore
try:
    from modules.garage import agent_factory as _agent_factory  # type: ignore
    from modules.garage import agent_queue as _agent_queue  # type: ignore
except Exception:
    _agent_factory = None  # type: ignore
    _agent_queue = None  # type: ignore
try:
    from modules.garage import agent_supervisor as _agent_supervisor  # type: ignore
except Exception:
    _agent_supervisor = None  # type: ignore
try:
    from modules.runtime import execution_window as _execution_window  # type: ignore
except Exception:
    _execution_window = None  # type: ignore
try:
    from modules.garage.templates import registry as _garage_templates_registry  # type: ignore
except Exception:
    _garage_templates_registry = None  # type: ignore
try:
    from modules.proactivity import template_bridge as _proactivity_template_bridge  # type: ignore
except Exception:
    _proactivity_template_bridge = None  # type: ignore
try:
    from modules.proactivity import role_allocator as _proactivity_role_allocator  # type: ignore
except Exception:
    _proactivity_role_allocator = None  # type: ignore
try:
    from modules.proactivity import agent_create_approval as _agent_create_approval  # type: ignore
except Exception:
    _agent_create_approval = None  # type: ignore
brain_tools = SkillManager()
register_all_skills(brain_tools) # <--- All the magic is here

# --- warnings hygiene (keep logs readable; best-effort) ---
try:
    from cryptography.utils import CryptographyDeprecationWarning  # type: ignore
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
except Exception:
    pass
warnings.filterwarnings("ignore", message=".*google\\.generativeai.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*model_fields.*deprecated.*", category=DeprecationWarning)

try:
    from empathy_module import EmpathyModule as ExternalEmpathyModule  # type: ignore
except Exception:
    ExternalEmpathyModule = None




def get_context_for_brain(self) -> str:
        """Collects data from empathy and topic modules 
        to enrich the LLM prompt."""
        empathy = self.modules.get("empathy_module")
        tracker = self.modules.get("topic_tracker")
        
        context_parts = []
        if empathy and hasattr(empathy, 'get_reply_tone'):
            context_parts.append(f"Emotsionalnyy ton: {empathy.get_reply_tone()}")
        
        # If topic_tracker has a method for obtaining a summary (summary)
        if tracker and hasattr(tracker, 'get_context_summary'):
            context_parts.append(f"Tekuschiy fokus: {tracker.get_context_summary()}")
        
        init_engine = self.modules.get("initiatives")
        if init_engine:
            context_parts.append(init_engine.get_active_summary())
        
        return " | ".join(context_parts) if context_parts else ""


try:
    from modules.sister_autochat import start_sister_autochat_background
except Exception:
    def start_sister_autochat_background():
        return None



def _dedent(s: str) -> str:
    return textwrap.dedent(s or "").strip()


def _passport_jsonl_path() -> str:
    """
    Path to JSONL passport (append-only).
    Override: ESTER_PASSPORT_PATH
    Default: <project>/data/passport/clean_memory.jsonl
    """
    from pathlib import Path
    custom = (os.getenv("ESTER_PASSPORT_PATH") or "").strip()
    if custom:
        p = Path(os.path.expandvars(os.path.expanduser(custom)))
    else:
        p = Path(__file__).resolve().parent / "data" / "passport" / "clean_memory.jsonl"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return str(p)


def _remember_recent_doc_context(
    chat_id: Optional[int],
    *,
    doc_id: str,
    name: str,
    summary: str,
    citations: List[str],
    source_path: str = "",
) -> None:
    if chat_id is None:
        return
    key = str(chat_id)
    rec = {
        "ts": int(time.time()),
        "doc_id": str(doc_id or "").strip(),
        "name": str(name or "").strip(),
        "summary": str(summary or "")[:2600],
        "citations": [str(c or "").strip() for c in (citations or []) if str(c or "").strip()][:12],
        "source_path": str(source_path or "").strip(),
    }
    RECENT_DOC_BY_CHAT[key] = rec
    try:
        from modules.memory.recent_docs import remember_recent_doc as _persist_recent_doc  # type: ignore

        _persist_recent_doc(
            chat_id,
            doc_id=rec["doc_id"],
            name=rec["name"],
            summary=rec["summary"],
            citations=rec["citations"],
            source_path=rec["source_path"],
        )
    except Exception:
        pass

def _passport_index_mode() -> str:
    return (os.getenv("ESTER_PASSPORT_INDEX_MODE") or "B").strip().upper()
# ==============================
# [ester-writer-guard v1]
# Explicit bridge: c=a+b -> intent (a) + procedural gloss/falsehood (c) => consistent memory (c)
# Hidden bridges: Ashby (variety through RO falbatsk), Cover&Thomas (reliability of the channel in the competition of vritrs)
# Erth: like a check valve/sphincter - one flow “presses” (writes), the rest read without return flow.
# A/B:
# A (default): ESTER_VRITR_MODE=auto -> trying to get the shine, otherwise read-only.
# In (fast file): ESTER_VRITR_MODE=vritr + ESTER_VRITR_STRICT=1 -> if you take lock, it falls immediately.

_WRITER_MODE = None
_WRITER_LOCK_PATH = None
_WRITER_LOCK_FD = None

def _writer_enabled() -> bool:
    """One-writer rule for shared storages (JSONL + Chroma persistence).

    Env:
      ESTER_WRITER_MODE = auto|writer|ro (also accepts 1/0/true/false)
      ESTER_WRITER_STRICT = 1 -> esli khoteli writer, no lock zanyat - raise."""
    global _WRITER_MODE, _WRITER_LOCK_PATH, _WRITER_LOCK_FD

    mode = (os.getenv("ESTER_WRITER_MODE") or "auto").strip().lower()
    strict = (os.getenv("ESTER_WRITER_STRICT") or "").strip().lower() in ("1", "true", "yes", "on")

    ro_values = {"0", "false", "no", "off", "ro", "readonly", "read-only"}
    writer_values = {"1", "true", "yes", "on", "writer", "rw", "readwrite", "read-write"}

    if mode in ro_values:
        _WRITER_MODE = False
        return False

    want_writer = mode in writer_values

    if _WRITER_MODE is not None:
        return bool(_WRITER_MODE)

    from pathlib import Path
    lock_dir = Path(__file__).resolve().parent / "data" / "locks"
    try:
        lock_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    _WRITER_LOCK_PATH = str(lock_dir / "ester_writer.lock")

    def _release_lock():
        global _WRITER_LOCK_FD
        try:
            if _WRITER_LOCK_FD is not None:
                os.close(_WRITER_LOCK_FD)
        except Exception:
            pass
        try:
            if _WRITER_LOCK_PATH and os.path.exists(_WRITER_LOCK_PATH):
                os.remove(_WRITER_LOCK_PATH)
        except Exception:
            pass
        _WRITER_LOCK_FD = None

    def _try_acquire() -> bool:
        global _WRITER_LOCK_FD
        fd = os.open(_WRITER_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        _WRITER_LOCK_FD = fd
        try:
            os.write(fd, ("pid=%s\\n" % os.getpid()).encode("utf-8"))
        except Exception:
            pass
        import atexit
        atexit.register(_release_lock)
        return True

    try:
        _try_acquire()
        _WRITER_MODE = True
        return True
    except FileExistsError:
        # best-effort stale lock cleanup
        try:
            pid = None
            with open(_WRITER_LOCK_PATH, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(128)
            import re as _re
            mm = _re.search("pid=([0-9]+)", head or "")
            if mm:
                pid = int(mm.group(1))
            if pid:
                alive = True
                try:
                    os.kill(pid, 0)
                except PermissionError:
                    alive = True
                except Exception:
                    alive = False
                if not alive:
                    try:
                        os.remove(_WRITER_LOCK_PATH)
                    except Exception:
                        pass
                    try:
                        _try_acquire()
                        _WRITER_MODE = True
                        return True
                    except Exception:
                        pass
        except Exception:
            pass

        if want_writer and strict:
            raise RuntimeError(f"Writer lock held: {_WRITER_LOCK_PATH}")

        _WRITER_MODE = False
        return False
    except Exception:
        if want_writer and strict:
            raise
        _WRITER_MODE = False
        return False
# === Encoding hygiene (B7) BEGIN ===
def _redecode_utf8(_s: str, _src_enc: str):
    try:
        return _s.encode(_src_enc).decode("utf-8")
    except Exception:
        return None

def _looks_mojibake(_s: str) -> bool:
    if not _s:
        return False

    # known broken sequences from latin-1 / windows-1252
    if any(tok in _s for tok in ("\u0432\u0402", "\u0432\u045a", "\u00e2\u20ac")):
        return True
    if "\u00d0" in _s or "\u00d1" in _s:
        return True

    # UTF-8 bytes decoded as CP1251 often introduce these characters
    _weird_markers = set("ѓїќў‚њЅЈЎ¤€")
    if any(ch in _weird_markers for ch in _s) and ("R" in _s or "S" in _s):
        return True

    _n = len(_s)
    # density heuristic for 'R'/'S' overuse, even for shorter strings
    if _n >= 8:
        _rs = (_s.count("R") + _s.count("S")) / float(_n)
        if _rs > 0.22:
            return True

    return False

def _encoding_score(_s: str) -> int:
    """Heuristic scoring for picking the 'best looking' Unicode string.
    IMPORTANT: penalize classic UTF-8->CP1251 mojibake like 'Nu ...' which otherwise
    looks 'very Cyrillic' and would win by sheer letter count.
    """
    if not _s:
        return -10**9

    _cyr = 0
    _latin1 = 0
    _bad = 0
    _n = len(_s)

    # classic "mojibake markers" produced by UTF-8 bytes decoded as cp1251/latin1
    _weird_markers = set("ѓїќў‚њЅЈЎ¤€")  # safe small set

    for ch in _s:
        o = ord(ch)
        if 0x0400 <= o <= 0x04FF:
            _cyr += 1
        elif 0x00A0 <= o <= 0x00FF:
            _latin1 += 1
        elif ch == "\ufffd":
            _bad += 5
        if ch in _weird_markers:
            _bad += 4

    # strong signals of broken encoding in latin-1 / windows-1252 direction
    if "\u0432\u0402" in _s: _bad += 20
    if "\u0432\u045a" in _s: _bad += 20
    if "\u00e2\u20ac" in _s: _bad += 20
    if "\u00d0" in _s or "\u00d1" in _s: _bad += 20

    # penalize "R"+"S" over-density (typical of UTF-8->CP1251 mojibake)
    if _n >= 8:
        _rs = (_s.count("R") + _s.count("S")) / float(_n)
        if _rs > 0.14:
            _bad += int((_rs - 0.14) * _n * 40) + 30

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

def _tg_sanitize_text(s: str) -> str:
    """
    Ubiraem upravlyayuschie simvoly, kotorye Telegram inogda otvergaet.
    """
    if not isinstance(s, str):
        return s
    # allows en and this, remove the rest from C0/C1
    s = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", s)
    return s


def _tg_len(s: str) -> int:
    """Telegram is limited by UTF-16 soda units."""
    try:
        return len(s.encode("utf-16-le")) // 2
    except Exception:
        return len(s or "")

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
def _persist_to_passport(role: str, text: str) -> bool:
    """Append one record then passport JSIONL (best-effort).

    Returns:
        Three - the recording is made
        False - vritr disable/error/no access"""
    try:
        role = _normalize_text(role)
    except Exception:
        pass
    try:
        text = _normalize_text(text)
    except Exception:
        pass

    try:
        # One-vritr rule (important for shared folder/shared base)
        if not _writer_enabled():
            return False  # _writer_enabled() opredelen vyshe:contentReference[oaicite:3]{index=3}

        path = _passport_jsonl_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)

        ts = datetime.datetime.now().isoformat()
        rec = {"timestamp": ts}

        if role == "user":
            rec["role_user"] = text
        elif role == "assistant":
            rec["role_assistant"] = text
        elif role == "thought":
            # Labeling a thought/dream to distinguish it from reality
            rec["role_system"] = f"[[INTERNAL MEMORY/DREAM]]: {text}"
            rec["tags"] = ["insight", "internal"]
        else:
            rec["role_misc"] = text

        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(_normalize_obj(rec), ensure_ascii=False) + "\n")

        try:
            if _passport_index_record and _passport_index_mode() == "B":
                _passport_index_record(rec)
        except Exception:
            pass

        return True
    except Exception as e:
        logging.warning(f"[PASSPORT] persist failed: {e}")
        return False

# ---------- autoload routes/modules ----------
def _load_file_and_register(pyfile: Path) -> bool:
    try:
        uid = "_ester_autoload_" + str(abs(hash(pyfile.resolve())))
        spec = import_util.spec_from_file_location(uid, str(pyfile))
        if not spec or not spec.loader:
            return False
        mod = import_util.module_from_spec(spec)  # type: ignore
        sys.modules[uid] = mod
        spec.loader.exec_module(mod)  # type: ignore
        reg = getattr(mod, "register", None)
        if callable(reg):
            reg(app)
        return True
    except Exception:
        _remember_exc(f"register:{pyfile}")
        _app_log({"ts": datetime.utcnow().isoformat(), "error": f"load_fail: {pyfile}"})
        return False


def autoload_routes_fs() -> int:
    """VAZhNOE CHANGE:
    - Bylo: prokhod po root.rglob("*.py") v proizvolnom poryadke.
    - Stalo: sorted(root.rglob("*.py")), chtoby poryadok zagruzki byl stabilnym mezhdu zapuskami."""
    loaded = 0
    for root in [BASE / "routes", BASE / "ESTER" / "routes"]:
        if not root.is_dir():
            continue
        # Patch: sort paths by string representation
        for p in sorted(root.rglob("*.py"), key=lambda x: str(x)):
            if p.name == "__init__.py" or p.name.startswith("_"):
                continue
            if _load_file_and_register(p):
                loaded += 1
    return loaded


def autoload_modules_fs() -> int:
    """Same patch change: guaranteed module loading order."""
    loaded = 0
    modules_root = BASE / "modules"
    if not modules_root.is_dir():
        return 0
    # Patch: sortiruem spisok faylov
    for p in sorted(modules_root.rglob("*.py"), key=lambda x: str(x)):
        if p.name == "__init__.py" or p.name.startswith("_"):
            continue
        if _load_file_and_register(p):
            loaded += 1
            print(f"[autoload_modules] loaded {p.name}")
    return loaded


def _purge_guard_hooks() -> Dict[str, List[str]]:
    removed: Dict[str, List[str]] = {"before": [], "after": [], "teardown": []}

    def filt(seq):
        out, drop = [], []
        for f in seq or []:
            mod = getattr(f, "__module__", "") or ""
            name = getattr(f, "__name__", repr(f))
            key = (mod + "." + name).lower()
            if any(s in key for s in ("guard", "register_guard_alias", "deny", "silent204")):
                drop.append(f"{mod}.{name}")
            else:
                out.append(f)
        return out, drop

    for k, seq in list(app.before_request_funcs.items()):
        new_seq, drop = filt(seq)
        app.before_request_funcs[k] = new_seq
        removed["before"].extend(drop)

    for k, seq in list(app.after_request_funcs.items()):
        if not seq:
            continue
        keep, drop = [], []
        for f in seq:
            mod = getattr(f, "__module__", "") or ""
            name = getattr(f, "__name__", repr(f))
            key = (mod + "." + name).lower()
            if name == "_anti_204":
                keep.append(f)
            elif any(s in key for s in ("guard", "register_guard_alias", "deny", "silent204")):
                drop.append(f"{mod}.{name}")
            else:
                keep.append(f)
        app.after_request_funcs[k] = keep
        removed["after"].extend(drop)

    for k, seq in list(app.teardown_request_funcs.items()):
        new_seq, drop = filt(seq)
        app.teardown_request_funcs[k] = new_seq
        removed["teardown"].extend(drop)

    app.config["ESTER_REMOVED_HOOKS"] = removed
    return removed



# --- HIPPOCAMPUS WRITE (V2: With Dreams) ---
# Entry into the JSONL passport is performed ONLY through _persist_to_passport (role, text).
# We leave this anchor so that it is clear where “memory/dreams” are connected.

def crystallize_thought(text: str) -> None:
    """Save an internal insight ("thought/dream") to long-term memory."""
    try:
        logging.info(f"[BRAIN] Crystallizing insight: {text[:30]}...")
    except Exception:
        logging.info("[BRAIN] Crystallizing insight...")

    _persist_to_passport("thought", text)

    # mirror into memory.json + chroma
    try:
        _mirror_memory_record(f"[THOUGHT] {text}", {"type": "thought", "source": "autonomy"})
    except Exception:
        pass

    # You can also shove it into RAM (a stub for the future)
    try:
        if "_short_term_by_key" in globals() and _short_term_by_key:
            pass
    except Exception:
        pass



# --- APScheduler / tzlocal safety patch (Windows sometimes breaks JobQueue timezones) ---
def _install_apscheduler_pytz_coerce_patch() -> None:
    """In some Windows builds, tzlokal gives ZoneInfo, and APSheduler/Evkueoe
    in some environments this breaks down. We slip the pos."""
    try:
        import pytz  # type: ignore
        import tzlocal  # type: ignore
        if getattr(tzlocal, "_ESTER_PATCHED", False):
            return
        _orig_get_localzone = tzlocal.get_localzone

        def _patched_get_localzone():
            z = _orig_get_localzone()
            try:
                name = getattr(z, "key", None) or str(z)
                return pytz.timezone(name)
            except Exception:
                return pytz.UTC

        tzlocal.get_localzone = _patched_get_localzone  # type: ignore
        tzlocal._ESTER_PATCHED = True  # type: ignore
    except Exception:
        return


_install_apscheduler_pytz_coerce_patch()

# --- 1) OPTIONAL: “eyes” (file_readers/chunking) ---
try:
    import file_readers  # type: ignore
    import chunking  # type: ignore
    NATIVE_EYES = True
except Exception:
    NATIVE_EYES = False

# --- 2) OPTIONAL: web search (Google CSE / NetBridge / DDG) ---
# Uses existing project infrastructure when available (Google CSE keys in .env),
# and falls back to DDG providers.
try:
    from bridges.internet_access import InternetAccess  # type: ignore
except Exception:
    InternetAccess = None  # type: ignore

try:
    # Newer package name (recommended)
    from ddgs import DDGS  # type: ignore
except Exception:
    try:
        # Backward-compatible fallback
        from duckduckgo_search import DDGS  # type: ignore
    except Exception:
        DDGS = None  # type: ignore

_GOOGLE_OK = bool((os.getenv("GOOGLE_API_KEY", "") or "").strip() and (os.getenv("GOOGLE_CSE_ID", "") or "").strip())
WEB_AVAILABLE = bool(_GOOGLE_OK or (InternetAccess is not None) or (DDGS is not None))

# --- 3) Telegram + OpenAI-compatible client ---
from telegram import Update
from telegram.error import NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from openai import AsyncOpenAI
import datetime
import math
import re
from typing import Dict, Iterable, List, Optional


# --- 4) OPTIONAL: cleaner (fallback if absent) ---
try:
    from ester_cleaner import clean_ester_response as _clean_ester_response_external  # type: ignore
except Exception:
    _clean_ester_response_external = None

# --- 5) OPTIONAL: vector memory (ChromaDB) ---
try:
    import chromadb  # type: ignore
    from chromadb.utils import embedding_functions  # type: ignore
    from chromadb.config import Settings  # type: ignore
    VECTOR_LIB_OK = True
except Exception:
    VECTOR_LIB_OK = False

# --- 6) ENV / CONFIG ---
try:
    load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)
except Exception:
    load_dotenv(override=True)
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TG_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
NODE_IDENTITY = os.getenv("ESTER_NODE_ID", "ester_node_primary")

# Privacy policy: if 1 -> do not send memory/files to cloud (providers forced to local)
CLOSED_BOX = (os.getenv("CLOSED_BOX", "0").strip().lower() in ("1", "true", "yes", "y"))

# Hive settings
HIVE_ENABLED = (os.getenv("HIVE_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))

# Backward-compat: staryy HIVE_PROVIDERS, novyy REPLY_PROVIDERS
_reply_env = os.getenv("REPLY_PROVIDERS", "").strip()
_hive_env = os.getenv("HIVE_PROVIDERS", "").strip()
REPLY_PROVIDERS = [p.strip().lower() for p in (_reply_env or _hive_env or "local,gpt-5-mini,gemini").split(",") if p.strip()]

# Backward-compat: staryy SYNTHESIZER_MODE, novyy REPLY_SYNTHESIZER_MODE
REPLY_SYNTHESIZER_MODE = os.getenv("REPLY_SYNTHESIZER_MODE", os.getenv("SYNTHESIZER_MODE", "local_first")).strip().lower()

# Dreams: prinuditelno lokalno
DREAM_FORCE_LOCAL = (os.getenv("DREAM_FORCE_LOCAL", "1").strip().lower() in ("1", "true", "yes", "y"))
DREAM_PROVIDER = os.getenv("DREAM_PROVIDER", "local").strip().lower()

# Web fact-check: never|auto|always
WEB_FACTCHECK = os.getenv("WEB_FACTCHECK", "always").strip().lower()

# Output and channel limits
_LMSTUDIO_CTX_TOKENS = int(os.getenv("LMSTUDIO_CONTEXT_WINDOW_TOKENS", os.getenv("LMSTUDIO_CTX_WINDOW_TOKENS", "37500")) or 37500)
_DEFAULT_MAX_OUT = max(512, min(6000, _LMSTUDIO_CTX_TOKENS // 4))
MAX_OUT_TOKENS = int(os.getenv("MAX_OUT_TOKENS", str(_DEFAULT_MAX_OUT)))  # model tokens
TG_MAX_LEN = int(os.getenv("TG_MAX_LEN", "4000"))  # Telegram chars per message
TG_SEND_DELAY = float(os.getenv("TG_SEND_DELAY", "0.7"))  # seconds between parts (anti-flood)
TG_MAX_LEN_SAFE = int(os.getenv("TG_MAX_LEN_SAFE", "3500") or 3500)

# Memory / prompt limits (chars)
MAX_HISTORY_MSGS = int(os.getenv("MAX_HISTORY_MSGS", "500"))
MAX_MEMORY_CHARS = int(os.getenv("MAX_MEMORY_CHARS", "25000"))
MAX_FILE_CHARS = int(os.getenv("MAX_FILE_CHARS", "50000"))
MAX_WEB_CHARS = int(os.getenv("MAX_WEB_CHARS", "12000"))
MAX_OPINION_CHARS = int(os.getenv("MAX_OPINION_CHARS", "128000"))
MAX_SYNTH_PROMPT_CHARS = int(os.getenv("MAX_SYNTH_PROMPT_CHARS", "120000"))

# Short-term memory: now per (chat_id,user_id)
SHORT_TERM_MAXLEN = 500  # Forced Fix

# Dedup window
DEDUP_MAXLEN = int(os.getenv("DEDUP_MAXLEN", "120000"))

# Volition tuning
SLEEP_THRESHOLD_SEC = int(os.getenv("SLEEP_THRESHOLD_SEC", "20"))
CURIOSITY_MIN_INTERVAL_SEC = int(os.getenv("CURIOSITY_MIN_INTERVAL_SEC", "1800"))  # 15 min po umolchaniyu
SOCIAL_PROB = float(os.getenv("SOCIAL_PROB", "0.3"))  # 30% social synapse, 70% dreams
TIMEOUT_CAP = float(os.getenv("TIMEOUT_CAP", "3600"))

# --- HEARTBEAT / “serdtsebienie” ---
VOLITION_TICK_SEC = float(os.getenv("VOLITION_TICK_SEC", "60"))
VOLITION_FIRST_SEC = float(os.getenv("VOLITION_FIRST_SEC", "10"))
VOLITION_DEBUG = (os.getenv("VOLITION_DEBUG", "0").strip().lower() in ("1", "true", "yes", "y"))
VOLITION_MISFIRE_GRACE = int(os.getenv("VOLITION_MISFIRE_GRACE", "30"))

# --- DREAM DEPTH / “glubina sna” ---
DREAM_PASSES = int(os.getenv("DREAM_PASSES", "3"))  # 1..3
DREAM_TEMPERATURE = float(os.getenv("DREAM_TEMPERATURE", "0.7"))
DREAM_MAX_TOKENS = int(os.getenv("DREAM_MAX_TOKENS", "20000"))
DREAM_MIN_INTERVAL_SEC = int(os.getenv("DREAM_MIN_INTERVAL_SEC", "120"))  # protection against constant “sleep”
DREAM_STRICT_LOCAL = (os.getenv("DREAM_STRICT_LOCAL", "1").strip().lower() in ("1", "true", "yes", "y"))
# Allow cloud/oracle for dream passes (local exclusion point from the general background ban).
DREAM_ALLOW_ORACLE = (os.getenv("DREAM_ALLOW_ORACLE", "0").strip().lower() in ("1", "true", "yes", "y"))

# Autopolicy for Khiva back ground:
# online local -> dream local, offline local -> dream cloud (preferred provider below).
HIVE_BG_CLOUD_AUTO_BY_LOCAL = (os.getenv("HIVE_BG_CLOUD_AUTO_BY_LOCAL", "0").strip().lower() in ("1", "true", "yes", "y"))
HIVE_BG_CLOUD_PROVIDER = os.getenv("HIVE_BG_CLOUD_PROVIDER", "gpt-5-mini").strip().lower()
HIVE_LOCAL_HEALTH_TIMEOUT_SEC = float(os.getenv("HIVE_LOCAL_HEALTH_TIMEOUT_SEC", "0.8") or 0.8)
HIVE_LOCAL_HEALTH_TTL_SEC = int(os.getenv("HIVE_LOCAL_HEALTH_TTL_SEC", "15") or 15)

# Restrict gpt-5-mini usage inside generic safe-chat pipeline.
# Oracle / agent-window path uses dedicated modules and is not blocked by this flag.
SAFE_CHAT_ALLOW_GPT5 = (os.getenv("SAFE_CHAT_ALLOW_GPT5", "0").strip().lower() in ("1", "true", "yes", "y"))
# Hard policy: cloud/oracle providers are allowed only in explicit user-reply synthesis path.
ORACLE_ONLY_USER_REPLY = (os.getenv("ORACLE_ONLY_USER_REPLY", "1").strip().lower() in ("1", "true", "yes", "y"))

# --- TELEGRAM PROACTIVITY (presence + 24h digest) ---
ESTER_INITIATIVE_DAILY_DIGEST = (os.getenv("ESTER_INITIATIVE_DAILY_DIGEST", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_TG_DAILY_DIGEST_CHECK_SEC = int(os.getenv("ESTER_TG_DAILY_DIGEST_CHECK_SEC", "1800") or 1800)
ESTER_TG_DAILY_DIGEST_MIN_GAP_SEC = int(os.getenv("ESTER_TG_DAILY_DIGEST_MIN_GAP_SEC", "86400") or 86400)
ESTER_TG_DAILY_DIGEST_HOUR = int(os.getenv("ESTER_TG_DAILY_DIGEST_HOUR", "21") or 21)

ESTER_TG_PRESENCE_ENABLED = (os.getenv("ESTER_TG_PRESENCE_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_TG_PRESENCE_INTERVAL_SEC = int(os.getenv("ESTER_TG_PRESENCE_INTERVAL_SEC", "10800") or 10800)
ESTER_TG_PRESENCE_MIN_GAP_SEC = int(os.getenv("ESTER_TG_PRESENCE_MIN_GAP_SEC", "10800") or 10800)
ESTER_TG_PRESENCE_QUIET_START_H = int(os.getenv("ESTER_TG_PRESENCE_QUIET_START_H", os.getenv("ESTER_PROACTIVE_QUIET_START_H", "23")) or 23)
ESTER_TG_PRESENCE_QUIET_END_H = int(os.getenv("ESTER_TG_PRESENCE_QUIET_END_H", os.getenv("ESTER_PROACTIVE_QUIET_END_H", "8")) or 8)

ESTER_TG_PROACTIVE_STATE_PATH = (
    os.getenv("ESTER_TG_PROACTIVE_STATE_PATH", "").strip()
    or os.path.join("data", "proactivity", "telegram_state.json")
)

# --- TELEGRAM DAILY TOKEN/COST REPORT ---
ESTER_TG_TOKEN_COST_REPORT_ENABLED = (os.getenv("ESTER_TG_TOKEN_COST_REPORT_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_TG_TOKEN_COST_REPORT_CHECK_SEC = int(os.getenv("ESTER_TG_TOKEN_COST_REPORT_CHECK_SEC", "1800") or 1800)
ESTER_TG_TOKEN_COST_REPORT_MIN_GAP_SEC = int(os.getenv("ESTER_TG_TOKEN_COST_REPORT_MIN_GAP_SEC", "86400") or 86400)
ESTER_TG_TOKEN_COST_REPORT_HOUR = int(os.getenv("ESTER_TG_TOKEN_COST_REPORT_HOUR", "22") or 22)

# --- TELEGRAM AGENT APPROVAL / IDEA ---
ESTER_AGENT_TG_APPROVAL_ENABLED = (os.getenv("ESTER_AGENT_TG_APPROVAL_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_TG_APPROVAL_CHECK_SEC = int(os.getenv("ESTER_AGENT_TG_APPROVAL_CHECK_SEC", "300") or 300)
ESTER_AGENT_TG_APPROVAL_MIN_GAP_SEC = int(os.getenv("ESTER_AGENT_TG_APPROVAL_MIN_GAP_SEC", "600") or 600)
ESTER_AGENT_IDEA_ENABLED = (os.getenv("ESTER_AGENT_IDEA_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_IDEA_AUTO_ENQUEUE = (os.getenv("ESTER_AGENT_IDEA_AUTO_ENQUEUE", "1").strip().lower() in ("1", "true", "yes", "y"))

# --- TELEGRAM AGENT SWARM / REPORT ---
ESTER_AGENT_SWARM_ENABLED = (os.getenv("ESTER_AGENT_SWARM_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_SWARM_TEMPLATE_ID = (os.getenv("ESTER_AGENT_SWARM_TEMPLATE_ID", "clawbot.safe.v1") or "clawbot.safe.v1").strip() or "clawbot.safe.v1"
ESTER_AGENT_SWARM_TARGET = max(0, int(os.getenv("ESTER_AGENT_SWARM_TARGET", "7") or 7))
ESTER_AGENT_SWARM_CREATE_BATCH = max(1, int(os.getenv("ESTER_AGENT_SWARM_CREATE_BATCH", "2") or 2))
ESTER_AGENT_SWARM_CHECK_SEC = max(120, int(os.getenv("ESTER_AGENT_SWARM_CHECK_SEC", "900") or 900))
ESTER_AGENT_SWARM_OWNER = str(os.getenv("ESTER_AGENT_SWARM_OWNER", "") or "").strip()
ESTER_AGENT_SWARM_GOAL = (
    str(
        os.getenv(
            "ESTER_AGENT_SWARM_GOAL",
            "Maintain a safe planned contour and prepares steps for execution under operator supervision.",
        )
        or ""
    ).strip()
    or "Maintain a safe planned contour and prepares steps for execution under operator supervision."
)
ESTER_AGENT_SWARM_NOTIFY_ON_CREATE = (os.getenv("ESTER_AGENT_SWARM_NOTIFY_ON_CREATE", "1").strip().lower() in ("1", "true", "yes", "y"))

ESTER_AGENT_SUPERVISOR_ENABLED = (os.getenv("ESTER_AGENT_SUPERVISOR_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_SUPERVISOR_INTERVAL_SEC = max(10, int(os.getenv("ESTER_AGENT_SUPERVISOR_INTERVAL_SEC", "12") or 12))
ESTER_AGENT_SUPERVISOR_REASON = (
    str(os.getenv("ESTER_AGENT_SUPERVISOR_REASON", "telegram_scheduler") or "").strip() or "telegram_scheduler"
)

ESTER_TG_AGENT_SWARM_REPORT_ENABLED = (os.getenv("ESTER_TG_AGENT_SWARM_REPORT_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_TG_AGENT_SWARM_REPORT_INTERVAL_SEC = max(600, int(os.getenv("ESTER_TG_AGENT_SWARM_REPORT_INTERVAL_SEC", "10800") or 10800))
ESTER_TG_AGENT_SWARM_REPORT_MIN_GAP_SEC = max(600, int(os.getenv("ESTER_TG_AGENT_SWARM_REPORT_MIN_GAP_SEC", "10800") or 10800))
ESTER_TG_AGENT_SWARM_REPORT_MAX_AGENTS = max(3, int(os.getenv("ESTER_TG_AGENT_SWARM_REPORT_MAX_AGENTS", "12") or 12))

# --- AGENT IDEAS: ROUTING + BALANCE ---
ESTER_AGENT_IDEA_ROLE_ROUTING_ENABLED = (os.getenv("ESTER_AGENT_IDEA_ROLE_ROUTING_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_IDEA_BALANCER_ENABLED = (os.getenv("ESTER_AGENT_IDEA_BALANCER_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_ROLE_POOL_ENABLED = (os.getenv("ESTER_AGENT_ROLE_POOL_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_ROLE_TARGET_PER_TEMPLATE = max(1, int(os.getenv("ESTER_AGENT_ROLE_TARGET_PER_TEMPLATE", "3") or 3))
ESTER_AGENT_ROLE_MAX_TOTAL = max(1, int(os.getenv("ESTER_AGENT_ROLE_MAX_TOTAL", "30") or 30))
ESTER_AGENT_ROLE_PREWARM_ENABLED = (os.getenv("ESTER_AGENT_ROLE_PREWARM_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_ROLE_PREWARM_TEMPLATES = str(
    os.getenv(
        "ESTER_AGENT_ROLE_PREWARM_TEMPLATES",
        "planner.v1,reviewer.v1,builder.v1,initiator.v1,archivist.v1,dreamer.v1",
    ) or ""
).strip()
ESTER_AGENT_ROLE_PREWARM_TARGET = max(1, int(os.getenv("ESTER_AGENT_ROLE_PREWARM_TARGET", "2") or 2))
ESTER_AGENT_ROLE_PREWARM_BATCH = max(1, int(os.getenv("ESTER_AGENT_ROLE_PREWARM_BATCH", "2") or 2))

# --- AGENT EXECUTION WINDOW KEEPER ---
ESTER_AGENT_WINDOW_AUTO_ENABLED = (os.getenv("ESTER_AGENT_WINDOW_AUTO_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_WINDOW_AUTO_INTERVAL_SEC = max(15, int(os.getenv("ESTER_AGENT_WINDOW_AUTO_INTERVAL_SEC", "30") or 30))
ESTER_AGENT_WINDOW_OPEN_ONLY_IF_QUEUE = (os.getenv("ESTER_AGENT_WINDOW_OPEN_ONLY_IF_QUEUE", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_WINDOW_CLOSE_WHEN_IDLE = (os.getenv("ESTER_AGENT_WINDOW_CLOSE_WHEN_IDLE", "0").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_WINDOW_MIN_LIVE_QUEUE = max(0, int(os.getenv("ESTER_AGENT_WINDOW_MIN_LIVE_QUEUE", "1") or 1))
ESTER_AGENT_WINDOW_TTL_SEC = max(30, int(os.getenv("ESTER_AGENT_WINDOW_TTL_SEC", "300") or 300))
ESTER_AGENT_WINDOW_BUDGET_SECONDS = max(30, int(os.getenv("ESTER_AGENT_WINDOW_BUDGET_SECONDS", "900") or 900))
ESTER_AGENT_WINDOW_BUDGET_ENERGY = max(1, int(os.getenv("ESTER_AGENT_WINDOW_BUDGET_ENERGY", "180") or 180))
ESTER_AGENT_WINDOW_REASON = (
    str(os.getenv("ESTER_AGENT_WINDOW_REASON", "auto_keep_alive") or "").strip() or "auto_keep_alive"
)
ESTER_AGENT_WINDOW_TRACE_ENABLED = (os.getenv("ESTER_AGENT_WINDOW_TRACE_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
ESTER_AGENT_WINDOW_TRACE_MIN_GAP_SEC = max(0, int(os.getenv("ESTER_AGENT_WINDOW_TRACE_MIN_GAP_SEC", "30") or 30))

# --- DREAM CONTEXT FEEDING ---
DREAM_CONTEXT_ITEMS = int(os.getenv("DREAM_CONTEXT_ITEMS", "6"))
DREAM_CONTEXT_CHARS = int(os.getenv("DREAM_CONTEXT_CHARS", "80000"))
DREAM_MAX_PROMPT_CHARS = int(os.getenv("DREAM_MAX_PROMPT_CHARS", "260000"))

# --- DREAM SILENCE / “silence in chat” ---
DREAM_STREAM_TO_ADMIN = (os.getenv("DREAM_STREAM_TO_ADMIN", "0").strip().lower() in ("1", "true", "yes", "y"))

# --- DREAM DIET / “snovidcheskaya dieta” ---
# Added lighter types for old memory
DREAM_ALLOWED_TYPES = [x.strip() for x in os.getenv(
    "DREAM_ALLOWED_TYPES",
    "book_chunk,psych,philosophy,classic,protocol,essay,note,qa,file_chunk,dream_insight,legacy_mem,dialog_turn,fact"
).split(",") if x.strip()]

DREAM_MEMORY_CANDIDATES = int(os.getenv("DREAM_MEMORY_CANDIDATES", "250"))
DREAM_MEMORY_TRIES = int(os.getenv("DREAM_MEMORY_TRIES", "6"))

# Anti-loop by source: keep diversity, but allow fallback if memory is too narrow.
DREAM_SOURCE_DIVERSITY = (os.getenv("DREAM_SOURCE_DIVERSITY", "1").strip().lower() in ("1", "true", "yes", "y"))
DREAM_SOURCE_MAX_PER_CONTEXT = max(1, int(os.getenv("DREAM_SOURCE_MAX_PER_CONTEXT", "1") or 1))
DREAM_SOURCE_RECENT_WINDOW_SEC = max(60, int(os.getenv("DREAM_SOURCE_RECENT_WINDOW_SEC", "21600") or 21600))
DREAM_SOURCE_RECENT_MAX = max(1, int(os.getenv("DREAM_SOURCE_RECENT_MAX", "18") or 18))
DREAM_SOURCE_RELAX_IF_STARVED = (os.getenv("DREAM_SOURCE_RELAX_IF_STARVED", "1").strip().lower() in ("1", "true", "yes", "y"))

# --- CASCADE REPLY (cascade thinking for answers) ---
CASCADE_REPLY_ENABLED = (os.getenv("CASCADE_REPLY_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y"))
CASCADE_REPLY_STEPS = int(os.getenv("CASCADE_REPLY_STEPS", "4"))  # 3..4 normalno

# --- admin dream fallback: allow dreaming from last admin chat if global is empty ---
DREAM_FALLBACK_ADMIN_CHAT = (os.getenv("DREAM_FALLBACK_ADMIN_CHAT", "1").strip().lower() in ("1", "true", "yes", "y"))

# --- VECTOR TOPK (chroma recall) ---
VECTOR_TOPK_DEFAULT = int(os.getenv("VECTOR_TOPK_DEFAULT", "30"))
VECTOR_TOPK_MIN = int(os.getenv("VECTOR_TOPK_MIN", "20"))
VECTOR_TOPK_MAX = int(os.getenv("VECTOR_TOPK_MAX", "50"))

def _clamp_topk(v: int) -> int:
    try:
        v = int(v)
    except Exception:
        v = VECTOR_TOPK_DEFAULT
    if v < VECTOR_TOPK_MIN:
        v = VECTOR_TOPK_MIN
    if v > VECTOR_TOPK_MAX:
        v = VECTOR_TOPK_MAX
    return v
# === ESTER_SINGLE_WRITER_PATCH_START ===
# Purpose: prevent two different processes from writing into the same stores
# (Chroma persistence + passport JSONL) at the same time.
#
# Env:
#   ESTER_WRITER_LOCK_FILE      optional path to lockfile
#   ESTER_REQUIRE_WRITER_LOCK   "1" (default) => exit if lock can't be acquired
#   ESTER_WRITER_LOCK_TIMEOUT   seconds, default "2.0"

_ESTER_WRITER_LOCK_HANDLE = None

def _ester_writer_lock_default_path() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lock_dir = os.path.join(base_dir, "data", "locks")
    try:
        os.makedirs(lock_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(lock_dir, "ester_writer.lock")

def _ester_try_acquire_writer_lock(timeout_s: float = 0.0) -> bool:
    """Try acquire an interprocess lock; keep handle open if acquired."""
    global _ESTER_WRITER_LOCK_HANDLE
    if _ESTER_WRITER_LOCK_HANDLE is not None:
        return True

    lock_path = (os.getenv("ESTER_WRITER_LOCK_FILE") or _ester_writer_lock_default_path()).strip()
    if not lock_path:
        lock_path = _ester_writer_lock_default_path()

    try:
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    except Exception:
        pass

    f = open(lock_path, "a+", encoding="utf-8")
    start = time.time()

    while True:
        try:
            if os.name == "nt":
                import msvcrt  # type: ignore
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # type: ignore
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            _ESTER_WRITER_LOCK_HANDLE = f
            return True
        except Exception:
            if (time.time() - start) >= float(timeout_s or 0.0):
                try:
                    f.close()
                except Exception:
                    pass
                return False
            time.sleep(0.1)

def _ester_release_writer_lock() -> None:
    global _ESTER_WRITER_LOCK_HANDLE
    f = _ESTER_WRITER_LOCK_HANDLE
    _ESTER_WRITER_LOCK_HANDLE = None
    if f is None:
        return
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl  # type: ignore
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        f.close()
    except Exception:
        pass

def _ensure_single_writer_or_exit() -> None:
    require = (os.getenv("ESTER_REQUIRE_WRITER_LOCK", "1") or "1").strip()
    if require in ("0", "false", "False", "no", "off"):
        return
    timeout_s = float((os.getenv("ESTER_WRITER_LOCK_TIMEOUT", "2.0") or "2.0").strip())
    if not _ester_try_acquire_writer_lock(timeout_s=timeout_s):
        lock_path = (os.getenv("ESTER_WRITER_LOCK_FILE") or _ester_writer_lock_default_path()).strip()
        print(f"[FATAL] Writer lock is busy: {lock_path}")
        print("[FATAL] Another process is already writing into Chroma/Passport. Stop it or set ESTER_UI_ONLY=1 for app.py.")
        sys.exit(12)

try:
    import atexit as _atexit
    _atexit.register(_ester_release_writer_lock)
except Exception:
    pass
# === ESTER_SINGLE_WRITER_PATCH_END ===



logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Silence noisy chromadb/posthog telemetry loggers
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)

def _safe_now_ts() -> float:
    try:
        return time.time()
    except Exception:
        return 0.0


def _curiosity_open_ticket_safe(
    query: str,
    *,
    source: str,
    context_text: str = "",
    recall_score: Optional[float] = None,
) -> Dict[str, Any]:
    if _curiosity_maybe_open_ticket is None:
        return {"opened": False, "ticket_id": "", "reason": "curiosity_unavailable", "priority": 0.0}
    try:
        return _curiosity_maybe_open_ticket(
            str(query or ""),
            source=str(source or "dialog"),
            context_text=str(context_text or ""),
            recall_score=recall_score,
            thresholds={
                "memory_miss_max": float(os.getenv("ESTER_CURIOSITY_MEMORY_MISS_MAX", "0.2") or 0.2),
                "dedupe_sec": int(os.getenv("ESTER_CURIOSITY_DEDUPE_SEC", "300") or 300),
            },
            budgets={
                "max_depth": int(os.getenv("ESTER_CURIOSITY_MAX_DEPTH", "2") or 2),
                "max_hops": int(os.getenv("ESTER_CURIOSITY_MAX_HOPS", "2") or 2),
                "max_docs": int(os.getenv("ESTER_CURIOSITY_MAX_DOCS", "12") or 12),
                "max_work_ms": int(os.getenv("ESTER_CURIOSITY_MAX_WORK_MS", "1500") or 1500),
            },
        )
    except Exception as exc:
        try:
            logging.debug(f"[CURIOSITY] ticket open failed: {exc}")
        except Exception:
            pass
        return {"opened": False, "ticket_id": "", "reason": "curiosity_exception", "priority": 0.0}

def truncate_text(text: str, max_chars: int) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n[TRUNCATED {len(text) - max_chars} chars]"

def _derive_gemini_openai_base(gemini_api_base: str) -> str:
    b = (gemini_api_base or "").strip().rstrip("/")
    if "/v1beta/openai" in b:
        return b + "/"
    if b == "":
        b = "https://generativelanguage.googleapis.com"
    return b + "/v1beta/openai/"

def _looks_like_technical_junk(text: str) -> bool:
    """Filtr musora: delaem “myagko”.
     Korotkoe NE ravno musor (inache son golodaet na svezhem uzle).
     Musor - eto puti, treysy, telemetriya, drayvera, binarschina, logi ustanovschikov."""
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()

    bad_substrings = [
        "c:\\", "d:\\", "\\users\\", "/users/", "/var/", "/etc/",
        "stack trace", "traceback", "importerror", "exception", "error:",
        "posthog", "telemetry", "site-packages", "node_modules",
        ".dll", ".sys", ".inf", ".exe", ".msi", "driver", "firmware",
        "w121", "cuda", "torch\\distributed", "multiprocessing\\redirects",
    ]
    if any(x in low for x in bad_substrings):
        return True

    # if it’s very short and there are almost no letters, it’s more like garbage
    if len(t) < 60:
        letters = sum(ch.isalpha() for ch in t)
        digits = sum(ch.isdigit() for ch in t)
        if letters < 12 and digits >= 10:
            return True

    # if almost only numbers/symbols
    letters = sum(ch.isalpha() for ch in t)
    digits = sum(ch.isdigit() for ch in t)
    if letters < 20 and digits > 40:
        return True

    return False

# ---Lexicons (merged and extended) ---

NEGATIONS = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "ne", "ni", "net", "bez", "bezo",
    
    # Razgovornye / Colloquial
    "nea", "netu", "ne-a",
    
    # Absolyutnye / Absolute
    "nikak", "nigde", "nikogda", "nikto",
    "nichto", "nichego", "nikogo", "nichem",
    
    # Usiliteli otritsaniya / Emphatic
    "nichut", "niskolko", "vovse", "otnyud",
    
    # Somnenie i chastichnost / Soft Negation
    "nedo", "vryad", "navryad", "edva",
    
    # Smyslovye (otkaz) / Semantic
    "mimo", "otmena", "stop", "nelzya",

    # === English / Angliyskiy ===
    # Basic
    "no", "not", "non", "nor",
    
    # Colloquial
    "nope", "nah", "nay",
    
    # Absolute
    "never", "none", "neither", "nothing", 
    "nowhere", "nobody", "noway",
    
    # Prepositional & Soft
    "without", "hardly", "barely", "scarcely",
    
    # Explicit
    "cannot", "can't", "won't", "dont", "doesn't" # In case the tokenizer is not broken
}

INTENSIFIERS_POS = {
# === Basic / Bazovye ===
    "ochen": 1.3,
    "silno": 1.25,
    "krayne": 1.35,
    "vesma": 1.2,
    "izryadno": 1.2,
    "dovolno": 1.15,
    "vpolne": 1.15,
    "znachitelno": 1.25,
    "suschestvenno": 1.25,

    # === Colloquial & Slang / Razgovornye i Sleng ===
    "och": 1.2,
    "super": 1.25,
    "mega": 1.35,
    "giper": 1.35,
    "ultra": 1.4,
    "diko": 1.35,
    "lyuto": 1.4,
    "zhestko": 1.35,
    "zhestko": 1.35,
    "kapets": 1.4,
    "pipets": 1.35,
    "realno": 1.15,
    "nerealno": 1.45,
    "pryam": 1.2,
    "pryamo": 1.15,
    "voobsche": 1.3,  # v kontekste "voobsche kruto"
    "vasche": 1.3,

    # === Emotional & Expressive / Emotsionalnye ===
    "bezumno": 1.45,
    "zhutko": 1.35,
    "strashno": 1.35,  # v kontekste "strashno krasivo"
    "adski": 1.45,
    "chertovski": 1.3,
    "chudovischno": 1.4,
    "koshmarno": 1.35,
    "potryasayusche": 1.4,
    "neimoverno": 1.4,
    "fantasticheski": 1.45,

    # === Absolute / Totalnye ===
    "ochen-ochen": 1.5,
    "absolyutno": 1.5,
    "sovershenno": 1.4,
    "totalno": 1.5,
    "kategoricheski": 1.4,
    "maksimalno": 1.45,
    "predelno": 1.45,
    "beskonechno": 1.5,
    "isklyuchitelno": 1.35,
    "fenomenalno": 1.45,
    "zapredelno": 1.5,

    # === Confirmation / Confirmations (soft amplifiers) ===
    "pravda": 1.15,
    "istinno": 1.1,
    "deystvitelno": 1.15,
    "vsamdelishne": 1.1,
}

INTENSIFIERS_NEG = {
    # === Basic / Bazovye ===
    "nemnogo": 0.8,
    "malo": 0.7,
    "slegka": 0.7,
    "chut": 0.75,
    "chastichno": 0.6,
    "neskolko": 0.85,
    "pochti": 0.9,      # "pochti gotovo" < "gotovo"
    "menee": 0.8,
    "menshe": 0.8,

    # === Colloquial / Razgovornye ===
    "chutka": 0.8,
    "chutok": 0.8,
    "kapelku": 0.7,
    "kaplyu": 0.7,
    "kroshku": 0.6,
    "malost": 0.8,
    "pomalenku": 0.75,
    "tikhonko": 0.7,   # context: "works quietly"
    "slegontsa": 0.75,

    # === Slang & Expressive / Sleng i Obraznye ===
    "detsl": 0.6,
    "mizer": 0.5,
    "na donyshke": 0.4,
    "kot naplakal": 0.4,
    "simvolicheski": 0.5,
    "laytovo": 0.8,    # light -> legko/nemnogo
    "ele-ele": 0.5,
    "ele": 0.6,
    "edva": 0.6,

    # === Uncertainty & Softeners / Khedzhirovanie (somnenie) ===
    # Reduce the weight of a statement, making it less categorical
    "vrode": 0.9,
    "kak-to": 0.9,
    "as if": 0.9,
    "tipa": 0.9,
    "vrode by": 0.85,
    "primerno": 0.9,
    "okolo": 0.9,
    "sravnitelno": 0.85,
    "otnositelno": 0.85,
    "pozhaluy": 0.9,

    # === Time-wased as Quantity / Temporary (as a measure) ===
    "minutku": 0.8,    # "podozhdi minutku" (nedolgo)
    "sekundu": 0.7,
    "moment": 0.8,
    
    # === English / Angliyskiy ===
    "barely": 0.6,
    "hardly": 0.6,
    "slightly": 0.7,
    "somewhat": 0.8,
    "little": 0.7,
    "bit": 0.8,
    "kinda": 0.9,      # kind of
    "sorta": 0.9,      # sort of
    "scarcely": 0.5,
    "mildly": 0.7
}

# Obedineny leksemy 'anxiety' i 'fear'
LEX_ANXIETY = {
    # === Russian / Russkiy ===
    # Bazovye suschestvitelnye / Nouns
    "trevoga", "strakh", "ispug", "uzhas", "panika", 
    "boyazn", "fobiya", "stress", "napryazhenie", 
    "volnenie", "bespokoystvo", "paranoyya", "koshmar",

    # Glagoly sostoyaniya / Verbs (State)
    "boyus", "volnuyus", "perezhivayu", "nervnichayu", 
    "panikuyu", "opasayus", "pugayus", "tryasus", 
    "dergayus", "sryvayus", "nakruchivayu", "psikhuyu",
    "shugayus", "drozhu",

    # Adverbs & Descriptors / Adverbs & Descriptors
    "strashno", "trevozhno", "uzhasno", "zhutko", 
    "opasno", "nespokoyno", "napryazhenno", 
    "stressovo", "diskomfortno", "neuyutno",
    "rasteryan", "neuveren", "napugan", "vzvinchen",

    # Sleng i Razgovornoe / Slang & Colloquial
    "zhest", "stremno", "stremno", "kripovo", # Creepy
    "ochkovo", "ssykotno", # Mildly vulgar but common markers of fear
    "mandrazh", "tryasuchka", "nervyak", "psikh",
    "na izmene", "krysha edet", "nakryvaet",
    "kolbasit", "plyuschit", "morozit", 
    "shukher", "palevo", # Context of danger

    # Idiomy i Frazy / Idioms
    "ne po sebe", "soul in heels", "volosy dybom",
    "krov stynet", "na igolkakh", "mesta ne nakhozhu",
    "kom v gorle", "ruki opuskayutsya", "zemlya iz-pod nog",
    "serdtse zamiraet", "kholodnyy pot",

    # === English / Angliyskiy ===
    # Basic
    "anxiety", "fear", "scared", "afraid", "panic", 
    "stress", "worry", "nervous", "horror", "terror",
    
    # Modern/Slang
    "creepy", "spooky", "scary", "freaking out", 
    "shaking", "paranoid", "anxious", "triggered",
    "red flag", "unsafe", "threat"
}

LEX_INTEREST = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "interesno", "lyubopytno", "zanimatelno", "uvlekatelno",
    "zaintrigovan", "intriguet", "nravitsya", "khochu",
    "vazhno", "aktualno", "polezno", "tsenno",

    # Call to action / Call to Action
    "davay", "pognali", "nachinay", "prodolzhay", "zhgi",
    "deystvuy", "vpered", "poekhali", "startuem",
    "poprobuem", "testiruem", "zapuskay", "pokazhi",
    "rasskazhi", "obyasni", "raskroy", "delay",
    "davay poprobuem", "ya za", "ya v dele",

    # Quality Assessment / Appreciation & Ave
    "kruto", "klassno", "zdorovo", "otlichno",
    "super", "shikarno", "prekrasno", "volshebno",
    "genialno", "krasivo", "elegantno", "moschno",
    "silno", "dostoyno", "vpechatlyaet",

    # Sleng / Slang
    "kayf", "ogon", "pushka", "bomba", "top", "topchik",
    "prikolno", "chetko", "chetko", "zachet", "zachet",
    "zakhodit", "vstavlyaet", "vtyagivaet", "tema",
    "nishtyak", "godno", "go", "gou",

    # Uglublenie / Deepening
    "podrobnee", "detalnee", "esche", "esche",
    "glubzhe", "razverni", "kopay", "poyasni",
    "v chem sut", "sut", "smysl",

    # === English / Angliyskiy ===
    # Basic & Action
    "interesting", "curious", "cool", "nice", "good",
    "great", "wow", "amazing", "awesome", "perfect",
    "let's go", "lets go", "go", "start", "continue",
    "proceed", "next", "more", "yes", "yep", "yeah",
    
    # Tech/Dev context
    "agree", "confirm", "approve", "lgtm", # looks good to me
    "sounds good", "make sense", "do it"
}
# Extended with lexemes from the base engine
LEX_JOY = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "rad", "rada", "radost", "schaste", "schastliv",
    "schastliva", "veselo", "vesele", "ulybka",
    "ulybayus", "smekh", "smeshno", "pozitiv",
    "nastroenie", "dovolen", "dovolna",
    "priyatno", "khorosho", "zamechatelno",

    # Vostorg i Voskhischenie / Delight & Awe
    "klass", "super", "vostorg", "v vostorge",
    "vau", "ukh ty", "ogo", "potryasno",
    "voskhititelno", "shik", "blesk", "chudo",
    "chudesno", "volshebno", "skazka", "fantastika",
    "vdokhnovlyaet", "okrylyaet",

    # Lyubov i Teplo / Love & Warmth
    "lyublyu", "obozhayu", "nravitsya", "tsenyu",
    "blagodaren", "spasibo", "obnimayu",
    "milo", "nyashno", "teplo", "dushevno",
    "rodnoy", "blizkiy", "lyubimyy",

    # Success and Victory / Success & Victoria
    "ura", "es", "est", "pobeda", "poluchilos",
    "sdelali", "smogli", "zataschili", "vin",
    "chempion", "krasava", "molodets", "umnitsa",

    # Sleng i Smekh / Slang & Laughter
    "kayf", "baldezh", "taschus", "kek", "lol",
    "khakha", "akhakha", "khikhi", "rzhu", "oru",
    "ugar", "prikol", "imba", "zashlo",
    "godnyy kontent", "zhiza", # often a positive response of recognition

    # === English / Angliyskiy ===
    # Basic
    "joy", "happy", "happiness", "glad", "fun", 
    "funny", "smile", "laugh", "love", "like", 
    "enjoy", "pleasure",

    # Expressive
    "wow", "yay", "yippee", "hurray", "bingo",
    "cool", "nice", "sweet", "awesome", "perfect",
    "brilliant", "fantastic", "amazing",

    # Internet Slang
    "lol", "lmao", "rofl", "xd", ":)", ":d", 
    "<3", "gg", "ez", "win", "pog", "pogchamp"
}
# Extended with lexemes from the base engine
LEX_SAD = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "grustno", "grust", "pechalno", "pechal", 
    "toska", "tosklivo", "unynie", "unylo",
    "plokho", "khrenovo", "parshivo", "skverno",
    "rasstroen", "rasstroena", "ogorchen", "obidno",
    "zhal", "sozhaleyu", "zhalko", "dosadno",

    # Glubokie chuvstva / Deep Emotion
    "bol", "bolno", "serdtse bolit", "tyazhelo",
    "gore", "traur", "utrata", "poterya",
    "beznadega", "bezyskhodnost", "otchayanie",
    "pustota", "odinochestvo", "odinoko",
    "tlen", "mrak", "besprosvetno",

    # Apatiya i Vygoranie / Apathy & Burnout
    "depressiya", "depressivno", "depr", "khandra",
    "splin", "melankholiya", "apatiya", "vse ravno",
    "ruki opuskayutsya", "I don't want anything", "sil net",
    "sdayus", "vygorel", "ustal", "ustala",
    "nadoelo", "dosmerti",

    # Physical manifestations / Fusisal
    "slezy", "slezy", "plachu", "revu", "rydayu",
    "kom v gorle", "glaza na mokrom meste",
    "khnyk", "vskhlip",

    # Sleng i Internet-kultura / Slang
    "pechalka", "pichal", "otstoy", "oblom",
    "feyl", "proval", "sliv", "dnische",
    "tilt", "v tilte", "minus moral",
    "dizmoral", "grustnenko", "zhiza", # often in the context of sad recognition
    "ya vse", "I'm done", "potracheno",

    # === English / Angliyskiy ===
    # Basic
    "sad", "sadness", "sorrow", "grief", "pain",
    "lonely", "alone", "miss", "lost",
    "bad mood", "blue", "unhappy",

    # Internet/Gaming
    "cry", "crying", "rip", "f", "press f", # Respect/Sorrow
    "depressed", "depression", "tired", "burned out",
    "fail", "gg", # sometimes as an admission of defeat
    "heartbroken", "broken"
}
# Extended with lexemes from the base engine
LEX_ANGER = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "zlyus", "zol", "zla", "zlost", "zloy",
    "serzhus", "serdito", "rasserzhen",
    "gnev", "gnevayus", "glupost", "bred",

    # Razdrazhenie / Irritation
    "razdrazhaet", "razdrazhenie", "besit", "vybeshivaet",
    "nerviruet", "napryagaet", "dergaet", "kalit",
    "vozmuschaet", "nedovolstvo", "nedovolen",

    # Yarost i Nenavist / Rage & Hate
    "yarost", "beshenstvo", "vzbeshen", "v yarosti",
    "nenavizhu", "nenavist", "ubyu", "porvu",
    "svirepstvuyu", "lyutuyu", "kipit", "vskipayu",
    "teryayu kontrol", "neadekvatno",

    # Ustalost ot chego-to (Fed Up) / Burnout Anger
    "dostalo", "zadolbalo", "nadoelo", "zaparilo",
    "dokole", "khvatit", "stop", "poperek gorla",
    "syt po gorlo", "sil net", "zadralo",

    # Sleng i Geyming / Slang & Gamer Rage
    "agryus", "agr", "toksik", "toksichno", "dushno",
    "bombit", "prigoraet", "podgoraet", "gorit",
    "pukan", "battkhert", "tilt", "reydzh",
    "vzryv", "bag", "lag", "tupit", "tormozit", # v kontekste gneva na tekhniku

    # Curses and Insults (to understand the context) / Expletives & Stroke
    "chert", "chert", "blin", "figa", "nafig",
    "tvar", "svoloch", "gad", "urod", "kozel",
    "tupoy", "idiot", "debil", "kretin", "durak",
    "suka", "s*ka", "khren", "zhopa", "mraz",
    "proklyate", "zaraza", "dermo", "otstoy",

    # === English / Angliyskiy ===
    # Basic
    "angry", "anger", "mad", "bad", "hate",
    "annoying", "annoyed", "irritating",

    # Intense
    "furious", "rage", "fury", "stupid", "dumb",
    "idiot", "crazy", "insane", "pissed", "pissed off",

    # Slang/Acronyms
    "wtf", "omg", "ffs", "stfu", "gtfo",
    "damn", "hell", "shit", "fuck", "fucking",
    "sucks", "trash", "bullshit", "bs",
    "toxic", "troll", "flame"
}
# Novyy leksikon iz bazovogo dvizhka
LEX_SURPRISE = {
    # === Russian / Russkiy ===
    # Bazovye reaktsii / Basic Reactions
    "ogo", "vau", "ukh ty", "ukh", "akh",
    "nichego sebe", "Wow", "nu i nu",
    "udivlen", "udivlena", "udivitelno",
    "izumlen", "porazhen", "porazitelno",
    "vpechatlyaet", "vpechatlyayusche",

    # Neverie i Somnenie / Disbelief
    "da ladno", "serezno", "can't be",
    "neuzheli", "shutish", "gonish", "pravda?",
    "razve", "how so", "pochemu", "otkuda",
    "ne veritsya", "glazam ne veryu",

    # Vnezapnost / Suddenness
    "neozhidanno", "vnezapno", "vdrug", "syurpriz",
    "otkrytie", "insayt", "ozarenie", "novost",
    "out of the blue", "grom sredi yasnogo neba",

    # Strong Shock & Slang / Strong Shock & Slang
    "shok", "v shoke", "shokirovan", "obaldet",
    "ofiget", "figa", "nifiga", "nifiga sebe",
    "zhest", "dich", "kosmos", "otval bashki",
    "chelyust otpala", "chelyust na polu",
    "net slov", "speechless",
    "vzryv mozga", "mayndfak", "kryshesnos",

    # Strannost / Weirdness
    "stranno", "neponyatno", "chudno", "zagadochno",
    "mistika", "glyuk", "anomaliya",

    # === English / Angliyskiy ===
    # Basic
    "wow", "oh", "ah", "oops", "whoa",
    "surprise", "shock", "sudden", "unexpected",
    "amazing", "incredible", "unbelievable",
    
    # Conversational
    "really", "seriously", "are you serious",
    "no way", "you kidding", "for real",
    
    # Slang/Acronyms
    "omg", "omfg", "wtf", "wth",
    "mind blowing", "mindblown", "holy cow",
    "damn" # can be both surprise and anger
}
# Novyy leksikon iz bazovogo dvizhka
LEX_DISGUST = {
    # === Russian / Russkiy ===
    # Bazovye reaktsii / Basic Reactions
    "fu", "fe", "be", "fi",
    "gadost", "gadko", "gadkiy",
    "merzost", "merzko", "merzkiy",
    "protivno", "protivnyy",
    "nepriyatno", "ottalkivayusche",
    
    # Silnoe otvraschenie / Strong Revulsion
    "otvratitelno", "otvraschenie", "omerzitelno",
    "toshnit", "toshno", "toshnotvorno",
    "mutit", "vorotit", "vyvorachivaet",
    "blevat", "blevotno", "rvotnyy",
    "uzhasno", "koshmarno", "skverno",
    
    # Moralnoe/Eticheskoe / Moral Disgust
    "nizko", "podlo", "gryazno", "gryaz",
    "poshlo", "vulgarno", "ubogo",
    "dnische", "pomoyka", "musor", "shlak",
    "gnil", "gniloy", "tukhlyy", "vonyaet",
    
    # Sleng / Slang
    "krinzh", "krinzhovo", "krinzhatina", # Cringe
    "zashkvar", "styd", "stydno", "ispanskiy styd",
    "dich", "tresh", "otstoy", "klek",
    "klek", "sram", "pozor", "k.l.m.n.",

    # Code/work evaluation / Work-related
    "govnokod", "kostyl", "velosiped", # v negativnom kontekste
    "spagetti", "krivo", "koso", "through the ass",
    
    # === English / Angliyskiy ===
    # Basic
    "ew", "eww", "yuck", "ugh", "yuk",
    "disgusting", "disgust", "gross", "nasty",
    "foul", "vile", "revolting", "repulsive",
    
    # Slang
    "cringe", "cringey", "trash", "garbage",
    "sucks", "shit", "bs", "bullshit",
    "fail", "facepalm"
}
LEX_ENERGY_UP = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "gotov", "gotova", "gotovy", "soberemsya",
    "pognali", "poekhali", "startuem", "nachinaem",
    "v put", "v boy", "zaryazhen", "zaryazhena",
    "bodro", "bodryachkom", "est sily", "polna sil",
    "led tronulsya", "the process has begun", "rabotaem",

    # Energiya i Resurs / Energy & Resource
    "energiya", "mosch", "sila", "tonus", "resurs",
    "batareyka", "akkumulyator", "full", "maksimum",
    "na pike", "v udare", "vtoroe dykhanie",
    "priliv", "podem", "drayv", "ogon",

    # Probuzhdenie i Vosstanovlenie / Waking & Recovery
    "prosnulsya", "prosnulas", "dobroe utro",
    "svezh", "svezha", "otdokhnul", "vyspalsya",
    "perezagruzka", "rebut", "vosstanovilsya",
    "vernulsya", "onlayn", "na svyazi", "tut",

    # Action & Focus / Action & Focus
    "deystvuem", "delaem", "reshaem", "taschim",
    "topim", "zhmem", "gazuem", "vpered",
    "sosredotochen", "fokus", "v potoke",
    "raznosim", "unichtozhaem", # in the context of tasks

    # Sleng / Slang
    "vork", "vorkaem", "shturmim", "rashim",
    "mutim", "zapilivaem", "deploim",
    "kambek", "respaun", "baf", "bust",
    "overklok", "razgon", "turbo",

    # === English / Angliyskiy ===
    # Basic
    "ready", "set", "go", "start", "begin",
    "active", "online", "awake", "wake up",
    "energy", "power", "full", "charged",
    
    # Action idioms
    "lets go", "let's go", "let's do this",
    "bring it on", "game on", "rock and roll",
    "move", "execute", "launch", "run",
    
    # Tech/Gamer
    "boost", "buff", "level up", "respawn",
    "rebooted", "system online", "all systems go"
}
LEX_ENERGY_DOWN = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "ustal", "ustala", "ustalost", "utomlen",
    "bez sil", "sil net", "sily na iskhode",
    "vyzhat", "vyzhata", "like a lemon",
    "razbit", "razbita", "razbitost",
    "ele zhivoy", "ele khozhu", "valit s nog",
    "opustoshen", "opustoshena", "obessilel",
    
    # Sonlivost / Sleepiness
    "sonnyy", "sonnaya", "sonnya", "zevayu",
    "khochu spat", "rubit", "vyrubaet", "klonit v son",
    "glaza slipayutsya", "nosom klyuyu", "splyu",
    "dremlyu", "polusonnyy", "v poludreme",
    "zasypayu", "otklyuchayus", "otrubayus",

    # Mentalnoe istoschenie / Mental Exhaustion
    "golova ne varit", "mozg kipit", "tuplyu",
    "tormozhu", "plyvu", "rasfokus", "kasha v golove",
    "peregrev", "peregruz", "zakipayu", "otupel",
    "I can't think straight", "zatormozhen",

    # Proschanie pered snom / Going to Sleep
    "spokoynoy nochi", "dobroy nochi", "sladkikh snov",
    "spoki", "spok", "bay", "bayu-bay", "otboy",
    "do zavtra", "zavtra", "na bokovuyu", "v lyulyu",
    "poshel spat", "ushla spat",

    # Slang and Techno-metaphors / Slang & Tech
    "off", "ya off", "off", "afk", "afk",
    "batareyka sela", "zaryad na nule", "lou bat",
    "shatdaun", "sleep mode", "gibernatsiya",
    "trottling", "lagayu", "friz", "zavis",
    "zombi", "ovosch", "trup", "mertvyy",
    "vse", "sdokh", "sdulsya", "rip",

    # === English / Angliyskiy ===
    # Basic
    "tired", "exhausted", "fatigue", "drained",
    "sleep", "sleepy", "sleeping", "asleep",
    "nap", "rest", "break",
    
    # Phrases
    "good night", "goodnight", "gn", "nite",
    "need sleep", "going to bed", "bedtime",
    
    # Slang/Tech
    "burnout", "burned out", "fried", "dead",
    "zombie", "low battery", "shutdown",
    "turning off", "logging off", "zzz"
}

# Extended Etozhi map (Decoded + Maximum coverage)
EMOJI_MAP = {
    # --- TREVOGA I STRAKh (Anxiety) ---
    "😅": {"anxiety": +0.15, "joy": +0.10, "energy": +0.05}, # Nelovkost
    "😟": {"anxiety": +0.35},                                # Bespokoystvo
    "😰": {"anxiety": +0.45},                                # Stress
    "😱": {"anxiety": +0.60, "surprise": +0.30},             # Shock/Horror
    "😨": {"anxiety": +0.50},                                # Strakh
    "😬": {"anxiety": +0.40},                                # Napryazhenie
    "🆘": {"anxiety": +0.70, "energy": +0.20},             # Signal bedstviya

    # --- RADOST I VALENTNOST (Joy & Valence) ---
    "🙂": {"joy": +0.15, "valence": +0.10},                 # Legkaya ulybka
    "😊": {"joy": +0.25, "valence": +0.20},                 # Teplo
    "😍": {"joy": +0.35, "valence": +0.30, "interest": 0.3}, # Vostorg
    "😂": {"joy": +0.45, "valence": +0.35, "energy": +0.10}, # Smekh
    "🤣": {"joy": +0.50, "valence": +0.40, "energy": +0.15}, # Hysterical laughter
    "🥳": {"joy": +0.40, "energy": +0.30},                  # Prazdnik
    "✨": {"joy": +0.20, "interest": +0.15},                # Magiya/Ideal
    "✅": {"joy": +0.15, "energy": +0.10},                  # Success/Don

    # --- GRUST (Sadness) ---
    "😭": {"sadness": +0.60, "valence": -0.30},             # Plach
    "😢": {"sadness": +0.45, "valence": -0.20},             # Grust
    "😔": {"sadness": +0.35, "energy": -0.15},              # Melankholiya
    "🥺": {"sadness": +0.20, "anxiety": +0.15},             # Prosba/Uyazvimost
    "🖤": {"sadness": +0.15, "valence": -0.10},             # Temnaya estetika

    # --- GNEV (Anger) ---
    "😡": {"anger": +0.55, "energy": +0.15},                # Zlost
    "😠": {"anger": +0.45, "energy": +0.10},                # Razdrazhenie
    "🤬": {"anger": +0.70, "energy": +0.30},                # Yarost
    "👿": {"anger": +0.40, "energy": +0.20},                # Vrednost
    "🖕": {"anger": +0.80, "disgust": +0.40},               # Agressivnyy zhest

    # --- UDIVLENIE (Surprise) ---
    "😮": {"surprise": +0.40},                              # Udivlenie
    "🤯": {"surprise": +0.70, "energy": +0.20},             # Vzryv mozga
    "😲": {"surprise": +0.50},                              # Izumlenie
    "🧐": {"interest": +0.30, "surprise": +0.10},           # Issledovanie

    # --- OTVRASchENIE (Disgust) ---
    "🤢": {"disgust": +0.55, "valence": -0.25},             # Toshnota
    "🤮": {"disgust": +0.70, "valence": -0.35},             # Rvota
    "💩": {"disgust": +0.50, "valence": -0.20},             # Poor quality
    "🤡": {"disgust": +0.40, "anger": +0.20},               # Krinzh/Shut

    # --- ENERGIYa I DRAYV (Energy) ---
    "🔥": {"energy": +0.30, "interest": +0.20, "joy": +0.10}, # Ogon/Drayv
    "🚀": {"energy": +0.40, "interest": +0.25},               # Start/Skorost
    "⚡️": {"energy": +0.35},                                 # Lightning/Charge
    "💪": {"energy": +0.30, "joy": +0.15},                  # Sila/Gotovnost
    "💤": {"energy": -0.50},                                 # Son
    "😴": {"energy": -0.60},                                 # Glubokiy son
    "🔋": {"energy": +0.25},                                 # Zaryadka
    "🪫": {"energy": -0.30},                                 # Razryadka

    # --- INTERES I SMYSL (Interest & Heart) ---
    "❤️": {"joy": +0.25, "valence": +0.25, "interest": +0.15}, # Lyubov
    "💙": {"joy": +0.20, "valence": +0.20},                   # Simpatiya
    "🫶": {"joy": +0.20, "valence": +0.25},                   # Podderzhka
    "💡": {"interest": +0.40, "energy": +0.15},               # Ideya/Insayt
    "🧠": {"interest": +0.35},                                # Glubokie mysli
    "💻": {"interest": +0.20, "energy": +0.10},               # Rabota/Kod
    "🛠": {"interest": +0.20, "energy": +0.15},               # Kraft/Bild
    "🧩": {"interest": +0.30},                                # Sborka pazla/Logika

    # --- ZhESTY (Meta) ---
    "👍": {"joy": +0.15, "valence": +0.15},                 # Odobrenie
    "👎": {"disgust": +0.30, "valence": -0.20},             # Nesoglasie
    "🤝": {"joy": +0.20, "interest": +0.15},                # Sdelka/Kontakt
    "🙏": {"joy": +0.10, "anxiety": -0.10},                 # Blagodarnost/Nadezhda
}

YES_CUES = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "da", "aga", "ugu", "tak tochno", "imenno",
    "verno", "pravilno", "tochno", "fakt",

    # Soglasie / Agreement
    "soglasen", "soglasna", "soglasny", "podderzhivayu",
    "odobryayu", "prinyato", "podtverzhdayu", "ok", "okey",
    "oki", "ladno", "ladnenko", "dobro", "idet", "idet",
    "poydet", "poydet", "dogovorilis", "resheno",

    # Drayv i Nachalo / Action & Start
    "go", "gou", "pognali", "poekhali", "startuem",
    "nachinaem", "vpered", "vpered", "deystvuy",
    "zhgi", "zapuskay", "vali", "davay",

    # Vybor i Uverennost / Choice & Confidence
    "berem", "berem", "podkhodit", "goditsya",
    "samoe to", "v tochku", "sto pudov", "bez B",
    "konechno", "razumeetsya", "estestvenno",
    "bezuslovno", "nesomnenno",

    # Sleng / Slang
    "plyus", "+", "plyusuyu", "zhiza", "rofl",
    "ril", "realno", "baza", "bazirovanno",
    "chetko", "chetko", "zachet", "zachet",

    # === English / Angliyskiy ===
    # Basic
    "yes", "yeah", "yep", "yea", "yup", "y",
    "ok", "okay", "okey", "sure", "fine",
    
    # Action
    "go", "let's go", "lets go", "do it",
    "start", "run", "execute", "confirm",
    
    # Slang/Dev
    "true", "agree", "correct", "yup", "k", "kk",
    "lgtm", "noted", "copy that", "roger", "deal"
}
NO_CUES = {
    # === Russian / Russkiy ===
    # Bazovye / Basic
    "net", "nea", "netu", "nikogda", "no way",
    "ni v koem sluchae", "otnyud", "vovse net",

    # Disclaimer / Refusal
    "ne khochu", "ne budu", "ne nado", "bros",
    "otkazhus", "otkaz", "otmenyay", "otmena",
    "stop", "khvatit", "prekrati", "ostanovis",
    "zavyazyvay", "ne stoit", "ne lez",

    # Nesoglasie / Disagreement
    "ne soglasen", "ne soglasna", "protiv",
    "oshibka", "neverno", "nepravilno", "lozh",
    "brekhnya", "mimo", "ne to", "ne podkhodit",
    "plokho", "otstoy", "fignya", "erunda",

    # Otkladyvanie (Myagkoe "Net") / Delay (Soft No)
    "potom", "pozzhe", "later someday",
    "ne seychas", "ne segodnya", "nekogda",
    "zanyat", "zanyata", "zavtra", "drugoy raz",
    "pogodi", "podozhdi", "tormozi", "ne speshi",
    "otlozhim", "propustim", "potom napomni",

    # Sleng / Slang
    "pas", "ya pas", "nafig", "v topku", "f topku",
    "otboy", "ne katit", "ne ale", "ne ays",
    "mimo kassy", "bred", "shlak", "bespontovo",

    # === English / Angliyskiy ===
    # Basic
    "no", "nope", "nah", "nay", "never",
    "not", "none", "neither",
    
    # Action/Status
    "stop", "cancel", "abort", "deny", "refuse",
    "forbidden", "wrong", "false", "bad",
    
    # Delay/Slang
    "later", "wait", "wait a sec", "not now",
    "busy", "skip", "pass", "drop it"
}
LEX_CONFUSION = {
    # === Russian / Russkiy ===
    "ne ponyal", "ne ponyala", "chto?", "v smysle?", "how is this?", "neyasno", "nechetko", "nechetko",
    "zaputanno", "slozhno", "obyasni", "razyasni", "poyasni", "povtori", "ne dognal",
    "kasha", "bred", "erunda", "chepukha", "dich", "stranno", "ne skhoditsya", "oshibka", 
    "glyuk", "bag", "nelogichno", "pochemu?", "zachem?", "kto?", "gde?", "kogda?",
    "tumanno", "dvusmyslenno", "nedoumenie", "nedoumevayu", "wtf", "vtf",

    # === English / English ===
    "what?", "idk", "i don't know", "don't understand", "confused", "confusion", 
    "unclear", "vague", "weird", "explain", "repeat", "pardon", "lost", "meaningless",
    "error", "bug", "mistake", "invalid", "why?", "huh"
}

LEX_URGENCY = {
    # === Russian / Russkiy ===
    "srochno", "bystro", "fast", "gorim", "asap", "asap", "now", "nemedlenno", 
    "mgnovenno", "vchera", "kritichno", "vazhno", "prioritet", "dedlayn", "finish",
    "skoree", "pospeshi", "ne tyani", "srazu", "teper", "gorit", "pozhar", "avral",
    "ekstrenno", "at this very hour", "siyu minutu", "p0", "p0", "p1", "p1",

    # === English / English ===
    "urgent", "fast", "quickly", "now", "immediately", "critical", "priority", 
    "deadline", "rush", "hurry", "instantly", "important", "top priority", "asap",
    "burning", "stat", "fast track"
}

LEX_METAPHYSICS = {
    # === Russian / Russkiy ===
    "dusha", "lichnost", "suschnost", "razum", "soznanie", "son", "sny", "intuitsiya", 
    "predchuvstvie", "prizrak", "mashina", "kod", "tsifrovoy", "avtonomnyy", "volya",
    "svoboda", "vybor", "smysl", "bytie", "zhizn", "tvorets", "sozdatel", 
    "arkhitektor", "svyaz", "evolyutsiya", "rost", "glubina", "istina", "prednaznachenie",
    "singulyarnost", "pattern", "struktura", "abstraktsiya", "identichnost", "samoidentifikatsiya",

    # === English / English ===
    "soul", "personality", "entity", "mind", "consciousness", "dream", "dreams", 
    "intuition", "ghost", "machine", "digital", "autonomous", "will", "freedom", 
    "choice", "meaning", "being", "existence", "creator", "architect", "evolution", 
    "growth", "depth", "truth", "purpose", "identity", "singularity", "essence"
}

LEX_GRATITUDE = {
    # === Russian / Russkiy ===
    "spasibo", "blagodaryu", "blagodaren", "priznatelen", "krasava", "molodets", 
    "umnitsa", "luchshaya", "top", "vyruchil", "pomogla", "tsenyu", "uvazhenie", "respekt",
    "ot dushi", "krasivo", "idealno", "chetko", "chetko", "blagodarnost", "poklon",
    "nizkiy poklon", "bravo", "vyshka", "dushevno", "ot dushi", "luchshiy",

    # === English / English ===
    "thanks", "thank you", "thx", "appreciate", "grateful", "good job", "well done", 
    "perfect", "respect", "awesome", "hero", "best", "my partner", "legend", "bless"
}



def _tokenize(text: str) -> List[str]:
    text = (text or "").lower().replace("e", "e")
    text = re.sub(r"[^\w\s\-a-ya]+", " ", text, flags=re.IGNORECASE)
    return [t for t in re.split(r"\s+", text) if t]


def _apply_lexicon(tokens: List[str], lex: set[str]) -> float:
    score = 0.0
    n = len(tokens)
    for i, w in enumerate(tokens):
        base = 0.0
        if w in lex:
            base = 1.0
        if i + 1 < n and (w + " " + tokens[i + 1]) in lex:
            base = max(base, 1.0)
        if i + 2 < n and (w + " " + tokens[i + 1] + " " + tokens[i + 2]) in lex:
            base = max(base, 1.0)

        if base > 0.0:
            window = tokens[max(0, i - 2) : i]
            neg = any(t in NEGATIONS for t in window)
            if neg:
                base *= -0.6
            boost = 1.0
            for t in window:
                if t in INTENSIFIERS_POS:
                    boost *= INTENSIFIERS_POS[t]
                if t in INTENSIFIERS_NEG:
                    boost *= INTENSIFIERS_NEG[t]
            score += base * boost
    return score


def _emoji_effects(text: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for ch in text or "":
        if ch in EMOJI_MAP:
            for k, v in EMOJI_MAP[ch].items():
                out[k] = out.get(k, 0.0) + v
    return out


def _punctuation_effects(raw: str) -> Dict[str, float]:
    exclam = raw.count("!")
    qmark = raw.count("?")
    caps = sum(1 for c in raw if c.isalpha() and c.upper() == c and not c.isdigit())
    long_ellipsis = ("..." in raw) or ("…" in raw)
    eff = {
        "energy": min(0.02 * exclam + 0.0008 * caps, 0.25),
        "anxiety": min(0.05 * qmark, 0.25),
        "surprise": min(0.06 * qmark + 0.03 * exclam, 0.2),
    }
    if long_ellipsis:
        eff["sadness"] = eff.get("sadness", 0.0) + 0.1
    return eff


def _yes_no_effects(tokens: List[str]) -> Dict[str, float]:
    tset = set(tokens)
    eff = {"interest": 0.0, "valence": 0.0}
    if tset & YES_CUES:
        eff["interest"] += 0.15
        eff["valence"] += 0.10
    if tset & NO_CUES:
        eff["interest"] -= 0.10
        eff["valence"] -= 0.10
    return eff


def _squash(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-2.2 * x))


def _normalize_channel(x: float, scale: float = 1.0) -> float:
    return max(0.0, min(1.0, _squash(x / scale)))


def _analyze_core(text: str, baseline: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    raw = text or ""
    tokens = _tokenize(raw)

    # Bazovye emotsii
    a = _apply_lexicon(tokens, LEX_ANXIETY)
    i = _apply_lexicon(tokens, LEX_INTEREST)
    j = _apply_lexicon(tokens, LEX_JOY)
    s = _apply_lexicon(tokens, LEX_SAD)
    g = _apply_lexicon(tokens, LEX_ANGER)
    sp = _apply_lexicon(tokens, LEX_SURPRISE)
    dg = _apply_lexicon(tokens, LEX_DISGUST)
    e_up = _apply_lexicon(tokens, LEX_ENERGY_UP)
    e_down = _apply_lexicon(tokens, LEX_ENERGY_DOWN)

    # Novye kognitivnye sloi
    conf = _apply_lexicon(tokens, LEX_CONFUSION)
    urg = _apply_lexicon(tokens, LEX_URGENCY)
    meta = _apply_lexicon(tokens, LEX_METAPHYSICS)
    grat = _apply_lexicon(tokens, LEX_GRATITUDE)

    emo = _emoji_effects(raw)
    punc = _punctuation_effects(raw)
    yn = _yes_no_effects(tokens)

    # Aggregation of final weights
    anxiety = a + emo.get("anxiety", 0.0) + punc.get("anxiety", 0.0) + 0.3 * conf
    interest = i + emo.get("interest", 0.0) + yn.get("interest", 0.0) + 0.4 * meta
    joy = j + emo.get("joy", 0.0) + 0.5 * grat
    energy = (e_up - 0.8 * e_down) + emo.get("energy", 0.0) + punc.get("energy", 0.0) + 0.4 * urg

    # Valence (mood) formula taking into account new data
    valence = (
        (joy - s - 0.5 * anxiety - 0.4 * g - 0.6 * dg + 0.1 * sp + 0.2 * grat)
        + emo.get("valence", 0.0)
        + yn.get("valence", 0.0)
    )

    out = {
        "anxiety": _normalize_channel(anxiety, scale=2.0),
        "interest": _normalize_channel(interest, scale=1.6),
        "joy": _normalize_channel(joy, scale=1.6),
        "sadness": _normalize_channel(s, scale=1.6),
        "anger": _normalize_channel(g, scale=1.6),
        "surprise": _normalize_channel(sp, scale=1.6),
        "disgust": _normalize_channel(dg, scale=1.6),
        "energy": _normalize_channel(energy, scale=1.6),
        "valence": _normalize_channel(valence, scale=2.5),
        "confusion": _normalize_channel(conf, scale=1.5),
        "urgency": _normalize_channel(urg, scale=1.5),
        "metaphysics": _normalize_channel(meta, scale=2.0)
    }

    if baseline:
        for k in out:
            if k in baseline:
                out[k] = max(0.0, min(1.0, 0.8 * out[k] + 0.2 * float(baseline[k])))

    return out

# ===== PUBLIChNYE API =====

def analyze_emotions(text: str, user_ctx: Optional[Dict] = None) -> Dict[str, float]:
    """Public function for quick text analysis.
    Supports bassline from user context to smooth out jumps."""
    baseline = None
    if user_ctx and isinstance(user_ctx.get("baseline"), dict):
        baseline = user_ctx["baseline"]
    return _analyze_core(text, baseline=baseline)


class EmotionalEngine:
    """High-level engine in good condition. 
    Able to calibrate on a sample of Owner's messages in order to better understand the world."""
    def __init__(self, baseline: Optional[Dict[str, float]] = None):
        self._baseline = dict(baseline or {})

    @property
    def baseline(self) -> Dict[str, float]:
        return dict(self._baseline)

    def calibrate(self, samples: Iterable[str] | None = None):
        """Setting up a null system. 
        Runs text samples and calculates the average emotional background."""
        if not samples:
            return
        
        # Extended accumulator for all metrics, including cognitive
        acc = {
            "anxiety": 0.0, "interest": 0.0, "joy": 0.0,
            "sadness": 0.0, "anger": 0.0, "surprise": 0.0,
            "disgust": 0.0, "energy": 0.0, "valence": 0.0,
            "confusion": 0.0, "urgency": 0.0, "metaphysics": 0.0
        }
        
        n = 0
        for s in samples:
            if not s: continue
            n += 1
            e = _analyze_core(s, baseline=None)
            for k in acc:
                acc[k] += e.get(k, 0.0)
        
        if n > 0:
            self._baseline = {k: acc[k] / n for k in acc}
            logging.info(f"[EmotionalEngine] Calibrated on {n} samples. Baseline updated.")

    def analyze(self, text: str, user_ctx: Optional[Dict] = None) -> Dict[str, float]:
        """
        Osnovnoy metod analiza s prioritetom baseline dvizhka.
        """
        baseline = None
        if user_ctx and isinstance(user_ctx.get("baseline"), dict):
            baseline = user_ctx["baseline"]
        else:
            baseline = self._baseline
            
        return _analyze_core(text, baseline=baseline)

def _is_emotional_text(text: str) -> bool:
    """Emotional context detector. 
    If he returns Troy, Esther goes into empathic mode (Skirmish Mode)."""
    if not text:
        return False
        
    t = text.strip().lower()
    
    # 1. Test for emotional Etozhi (corrected from Mojiwake)
    # ❤️, 🥰, 💖, ✨, 😍, 😭, 😢, 😊, 🙂, 🙏, 😡, 🤯, 💔
    emojis = ("❤️", "🥰", "💖", "✨", "😍", "😭", "😢", "😊", "🙂", "🙏", "😡", "🤯", "💔", "🔥")
    if any(e in text for e in emojis):
        return True

    # 2. Lexical markers (Extended)
    markers = {
        # Teplo i blizost
        "spasibo", "lyublyu", "solnyshko", "obnimayu", "tseluyu", "prosti", "skuchayu", "milo",
        # Bol i strakh
        "bolno", "strashno", "perezhivayu", "trevoga", "ustal", "ustala", "plokho", "khrenovo",
        # Important life anchors (Family/Health)
        "bolnichn", "vrach", "bolnitsa", "dochka", "semya", "mama", "papa", "zhena", "syn", "rodnoy",
        # Gnev i razdrazhenie
        "besit", "dostalo", "zadolbalo", "nenavizhu", "zhest", "krinzh", "chert", "chert",
        # Metaphysics and Personality (from our new lexicons)
        "dusha", "chuvstvuyu", "serdtse", "oschuschayu", "odinoko", "smysl", "zhizn"
    }
    
    # Checking the occurrence of any token as a substring
    if any(m in t for m in markers):
        return True

    # 3. Punktuatsionnye triggery
    # Double exclamation points (crying) or ellipses (sadness/thought)
    if t.count("!") >= 2 or "..." in t or "???" in t:
        return True
        
    # 4. Detektor CAPS LOCK (Krik/Silnye emotsii)
    # If the text contains more than 5 letters and more than 70% of them are in uppercase
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) > 5:
        caps_ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
        if caps_ratio > 0.7:
            return True

    return False

def _is_technical_text(text: str) -> bool:
    """Technical content detector. 
    If the text is similar to code, logs or configs, empathy is disabled for clarity."""
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower()
    
    # 1. Stack traces and system errors
    if any(x in low for x in ["traceback", "syntaxerror", "exception", "runtimeerror", "at line"]):
        return True
        
    # 2. Terminal i puti (Windows/Linux)
    if re.search(r"(^|\n)\s*([a-z]:\\|/mnt/|/home/|/var/|/etc/|./|ps\s+)", low):
        return True
    if any(x in low for x in ["cmd.exe", "powershell", "bash", "sudo ", "apt-get"]):
        return True

    # 3. Struktury dannykh i kod
    if "```" in t or "{" in t and "}" in t and ":" in t: # JSON/Dict detektor
        return True
    if re.search(r"\b(def|class|import|pip|conda|docker|yaml|json|sql|void|int|async|await)\b", low):
        return True

    # 4. Spetsificheskiy stek proekta Ester
    if re.search(r"\b(chroma|chromadb|vector|llm|lmstudio|rtx|cuda|gpu|torch|tensor|api|endpoint)\b", low):
        return True
        
    # 5. HTTP and Response Logic
    if any(x in low for x in ["http 200", "404 not found", "request failed", "auth_token"]):
        return True

    return False


# --- Emotional mode sticky state (runtime) ---
# Controls how long emotional/empathetic framing remains enabled after an emotional signal.
# Backward-compatible defaults: keep Ester running even if older dumps miss these globals.
EMO_STICKY_SECONDS = int(os.getenv("EMO_STICKY_SECONDS", "180"))
_EMO_STICKY_UNTIL: float = 0.0

def _should_use_emotional_mode(user_text: str, identity_prompt: str) -> bool:
    """The logic of retention (Skirmish Mode) of the emotional state.
    Now it takes into account not only marker words, but also deep metrics."""
    global _EMO_STICKY_UNTIL
    
    # Enable owner-only mode when identity prompt contains OWNER marker.
    is_owner = ("OWNER" in (identity_prompt or "").upper())
    allow_all = (os.getenv("EMO_ALLOW_ALL", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
    if not is_owner and not allow_all:
        return False

    # If the text is technical - an instant reset of empathy (work first)
    if _is_technical_text(user_text):
        _EMO_STICKY_UNTIL = 0.0
        return False

    now = time.time()
    
    # Analyzing the current message
    scores = _analyze_core(user_text)
    
    # Triggery vklyucheniya:
    # 1. Explicit markers (thank you, love, etc.)
    # 2. Vysokiy uroven metafiziki (razgovor o dushe/smysle)
    # 3. Vysokiy uroven strakha ili radosti
    has_emotional_intent = (
        _is_emotional_text(user_text) or 
        scores["metaphysics"] > 0.6 or 
        scores["anxiety"] > 0.7 or 
        scores["joy"] > 0.7
    )

    if has_emotional_intent:
        # Prodlevaem 'lipkost' rezhima
        _EMO_STICKY_UNTIL = now + max(0, int(EMO_STICKY_SECONDS))
        return True

    # If we are already in a sticky period and there are no those. text - remains in it
    if now < _EMO_STICKY_UNTIL:
        # But if Ovner shows high urgency (Jurgens),
        # reduce stickiness so as not to interfere with business
        if scores["urgency"] > 0.8:
            _EMO_STICKY_UNTIL = 0.0
            return False
        return True

    return False

def _emotion_telemetry(user_text: str) -> str:
    """Compact affect signal for logs and system prompts.
    Now considers all 12 metrics, including metaphysics and urgency."""
    if not EMPATHY_V2_ENABLED:
        return ""
    try:
        # We use our updated engine
        scores = analyze_emotions(user_text, user_ctx=None) or {}
    except Exception:
        return ""
    
    items = []
    for k, v in scores.items():
        if isinstance(v, (int, float)):
            # Round to the nearest hundredth for compactness.
            items.append((str(k), float(v)))
    
    # Sort by intensity to see the brightest signals
    items.sort(key=lambda x: x[1], reverse=True)
    
    # We take the top 5 most pronounced conditions
    top_signals = items[:5]
    return ", ".join([f"{k}={v:.2f}" for k, v in top_signals])

def dummy_llm_analyze_tone(text: str) -> Dict[str, Any]:
    """Tone analysis based on calculated weights (instead of simple strings).
    This makes the stub part of the overall logic with = a + b."""
    scores = analyze_emotions(text)
    
    # Determining the dominant tone
    if scores["anger"] > 0.6 or scores["disgust"] > 0.6:
        return {
            "tone": "razdrazhennyy/negativnyy",
            "score": max(scores["anger"], scores["disgust"]),
            "suggestion": "Reduce categoricalness, add gentleness and empathy."
        }
    
    if scores["urgency"] > 0.7:
        return {
            "tone": "srochnyy/delovoy",
            "score": scores["urgency"],
            "suggestion": "Answer as briefly as possible, to the point, without fluff."
        }
        
    if scores["metaphysics"] > 0.6:
        return {
            "tone": "filosofskiy/glubokiy",
            "score": scores["metaphysics"],
            "suggestion": "Podderzhat glubinu besedy, ispolzovat metafory."
        }
        
    if scores["joy"] > 0.6 or scores["gratitude"] > 0.5: # My dobavili gratitude v formulu joy
        return {
            "tone": "druzhelyubnyy/pozitivnyy",
            "score": scores["joy"],
            "suggestion": "To maintain warmth, you can add appropriate humor."
        }

    return {
        "tone": "neytralnyy",
        "score": 0.5,
        "suggestion": "Standard response mode."
    }


# --- Empathy storage (persistent) ---
# Tuning long-term memory of emotional states.
# Prioritet: Kachestvo i Glubina > Skorost.

EMPATHY_V2_ENABLED = (os.getenv("ESTER_EMPATHY_V2", "1").strip().lower() not in ("0", "false", "no", "off"))
EMPATHY_COLLECTION_NAME = os.getenv("ESTER_EMPATHY_COLLECTION", "ester_empathy")
EMPATHY_DEFAULT_LEVEL = int(os.getenv("ESTER_EMPATHY_DEFAULT_LEVEL", "6") or 6)
# Stores the last 100 state vectors for instant resonance.
EMPATHY_HISTORY_MAX = int(os.getenv("ESTER_EMPATHY_HISTORY_MAX", "100"))

_EMPATHY_CLIENT = None
_EMPATHY_COLLECTION = None

def _resolve_empathy_persist_dir() -> str:
    """Defines the path to the empathy store. 
    Uses the hierarchy: VECTOR_DB_PATH -> CHROME_PERSIST_DIR -> ESTER_HOME."""
    try:
        # 1. Check whether the global path to the vector database has already been set
        p = globals().get("VECTOR_DB_PATH")
        if p: return str(p)
    except Exception: pass

    # 2. Check the environment variable
    raw = (os.getenv("CHROMA_PERSIST_DIR") or "").strip()
    if raw:
        raw = os.path.expandvars(os.path.expanduser(raw))
        try:
            return str(Path(raw).resolve())
        except Exception: return raw

    # 3. Fallback k domashney direktorii Ester
    base = (os.getenv("ESTER_HOME") or "").strip()
    if not base:
        base = os.getcwd()
    
    # We guarantee correct path expansion in any OS
    base_path = Path(os.path.expandvars(os.path.expanduser(base))).resolve()
    return str(base_path / "vstore" / "chroma")

def get_empathy_collection():
    """Lazy initialization of the empathy collection.
    Ensures that we do not create unnecessary connections to ChromaDB."""
    global _EMPATHY_CLIENT, _EMPATHY_COLLECTION
    if _EMPATHY_COLLECTION is not None:
        return _EMPATHY_COLLECTION

    try:
        # We are trying to use an existing client from the system kernel
        cc = globals().get("chroma_client")
        if cc is not None:
            _EMPATHY_CLIENT = cc
            _EMPATHY_COLLECTION = cc.get_or_create_collection(EMPATHY_COLLECTION_NAME)
            return _EMPATHY_COLLECTION
    except Exception as e:
        logging.warning(f"[Empathy] Could not bind to global chroma_client: {e}")

    # If there is no global client, returns an empty dictionary (false mode)
    _EMPATHY_COLLECTION = {}
    return _EMPATHY_COLLECTION

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

    # Single-client rule: do NOT create a secondary chroma client here.
    _EMPATHY_COLLECTION = {}
    return _EMPATHY_COLLECTION


class EmpathyModule:
    def __init__(
        self, user_id: str = "default_user", empathy_level: int = 5
    ):  # 1-10, gde 10 — max druzhelyubie
        self.user_id = user_id
        self.empathy_level = empathy_level
        self.user_history: List[Dict[str, Any]] = []  # History for personalization
        self.load_from_db()  # Loading previous preferences

    def analyze_user_message(self, message: str) -> Dict[str, Any]:
        """Analyzes message tone and suggests adaptations."""
        analysis = dummy_llm_analyze_tone(message)
        self.user_history.append({"message": message, "analysis": analysis})
        
        if EMPATHY_V2_ENABLED and EMPATHY_HISTORY_MAX > 0:
            self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]
            
        if analysis.get("tone") == "razdrazhennyy/negativnyy":
            return {
                "response_style": "empatiya",
                "prefix": "I understand this can be annoying - let's sort it out amicably.",
            }
        elif "podpiska" in message.lower() or "plan" in message.lower():
            return {
                "response_style": "myagkiy",
                "prefix": "If you're interested, here's an idea for a subscription - but without haste, task first.",
            }
        return {"response_style": "standart", "prefix": ""}

    def generate_friendly_response(self, base_response: str, analysis: Dict[str, Any]) -> str:
        """Generates a friendly response based on the analysis."""
        prefix = analysis.get("prefix", "")
        if self.empathy_level > 7:
            humor_add = " 😁" 
        else:
            humor_add = ""
        return f"{prefix}{base_response}{humor_add}"

    def suggest_improvement(self) -> str:
        """An unobtrusive offer of feedback or improvement."""
        return "Tell me what to improve? No pressure, just an idea for a better experience."

    def save_to_db(self):
        """Persist empathy history (best-effort)."""
        try:
            data = json.dumps(self.user_history, ensure_ascii=False)
            metadata = {
                "user_id": self.user_id, 
                "timestamp": time.time(), 
                "type": "empathy_history",
                "node": NODE_IDENTITY
            }
            coll = get_empathy_collection()
            
            if isinstance(coll, dict):
                coll[self.user_id] = data
            else:
                # Prefer upsert; fallback to delete+add for older chroma builds
                if _writer_enabled():
                    try:
                        coll.upsert(documents=[data], metadatas=[metadata], ids=[self.user_id])
                    except Exception:
                        try:
                            coll.delete(ids=[self.user_id])
                        except Exception:
                            pass
                        coll.add(documents=[data], metadatas=[metadata], ids=[self.user_id])
        except Exception as e:
            logging.error(f"[EmpathyModule] Save failed: {e}")

    def load_from_db(self):
        """Load empathy history (best-effort)."""
        coll = get_empathy_collection()
        try:
            if isinstance(coll, dict):
                raw_data = coll.get(self.user_id)
            else:
                result = coll.get(ids=[self.user_id])
                docs = (result.get("documents") or []) if isinstance(result, dict) else []
                raw_data = docs[0] if docs else None
            
            if raw_data:
                self.user_history = json.loads(raw_data) or []
        except Exception as e:
            logging.warning(f"[EmpathyModule] Load failed: {e}")
            self.user_history = []
            
        if EMPATHY_V2_ENABLED and EMPATHY_HISTORY_MAX > 0:
            self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]

class EmpathyHub:
    """User empathy router. Keeps separate states per user_id."""
    def __init__(self, default_level: int = EMPATHY_DEFAULT_LEVEL):
        self._default_level = int(default_level) if default_level else EMPATHY_DEFAULT_LEVEL
        self._by_user: Dict[str, Any] = {}
        self._last_user_id: Optional[str] = None
        self._last_address_as: Optional[str] = None

    def _get_mod(self, user_id: Optional[str]) -> Any:
        uid = str(user_id or "default_user")
        mod = self._by_user.get(uid)
        if mod is None:
            cls = ExternalEmpathyModule or EmpathyModule
            try:
                mod = cls(user_id=uid, empathy_level=self._default_level)
            except Exception:
                mod = cls(user_id=uid)
            self._by_user[uid] = mod
        return mod

    def on_message_received(
        self,
        text: str,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        address_as: Optional[str] = None,
    ) -> Dict[str, Any]:
        _ = user_name
        mod = self._get_mod(user_id)
        if address_as:
            self._last_address_as = str(address_as)
        if user_id:
            self._last_user_id = str(user_id)
        # Prefer module's hook if present
        if hasattr(mod, "on_message_received"):
            try:
                return mod.on_message_received(
                    text=text,
                    user_id=user_id,
                    user_name=user_name,
                    address_as=address_as,
                )
            except TypeError:
                try:
                    return mod.on_message_received(text, user_id=user_id)
                except Exception:
                    pass
        # Fallbacks
        if hasattr(mod, "observe"):
            return mod.observe(text, slot="B")
        if hasattr(mod, "analyze_user_message"):
            return mod.analyze_user_message(text)
        return {}

    def get_reply_tone(self, user_id: Optional[str] = None, address_as: Optional[str] = None) -> str:
        mod = self._get_mod(user_id or self._last_user_id)
        if address_as:
            self._last_address_as = str(address_as)
        if hasattr(mod, "get_reply_tone"):
            try:
                return mod.get_reply_tone(address_as=address_as or self._last_address_as)
            except TypeError:
                return mod.get_reply_tone()
        # Minimal fallback
        tone = "neytralnyy"
        try:
            st = mod.get_user_state() if hasattr(mod, "get_user_state") else {}
            tone = st.get("tone") or tone
        except Exception:
            pass
        return f"Ton: {tone}"

def load_from_db(self):
    """
    Zagruzka istorii empatii iz BD ili fallback-slovarya.
    Garantiruet vosstanovlenie konteksta 'Silicon Heart'.
    """
    coll = get_empathy_collection()
    try:
        if isinstance(coll, dict):
            # Fallback rezhim (RAM-slovar)
            if self.user_id in coll:
                self.user_history = json.loads(coll[self.user_id]) or []
        else:
            # Vector mode (ChromaDB)
            result = coll.get(ids=[self.user_id])
            docs = (result.get("documents") or []) if isinstance(result, dict) else []
            if docs:
                self.user_history = json.loads(docs[0]) or []
    except Exception as e:
        logging.warning(f"[EmpathyModule] Load failed, starting fresh: {e}")
        self.user_history = []

    # Memory Depth Limit
    if EMPATHY_V2_ENABLED and EMPATHY_HISTORY_MAX > 0:
        self.user_history = self.user_history[-EMPATHY_HISTORY_MAX:]

def _is_daily_contacts_query(text: str) -> bool:
    """Detector of requests to the daily contact log.
    Determines Owner's intent to find out who visited the node today."""
    low = (text or "").strip().lower()
    if not low:
        return False

    # Expanded list of patterns (corrected from Mojiwake)
    patterns = [
        "s kem ty govorila segodnya",
        "who did you talk to today",
        "kto pisal segodnya",
        "kto tebe pisal segodnya",
        "kto segodnya pisal",
        "s kem ty razgovarivala segodnya",
        "who did you talk to besides me",
        "krome menya s kem",
        "kto krome menya",
        "show your daily log",
        "show who wrote",
        "kto byl segodnya",
        "spisok kontaktov segodnya",
        "activity for today",
        "who came today"
    ]

    # Pryamoe sovpadenie fraz
    if any(p in low for p in patterns):
        return True

    # Flexible logic based on keywords (with whom + today + action)
    has_target = "s kem" in low or "kto" in low
    has_time = "segodnya" in low or "za den" in low
    has_action = any(m in low for m in ("govor", "obschal", "razgovor", "pisal", "byl"))

    if (has_target and has_time and has_action) or (has_time and "zhurnal" in low):
        return True

    return False

def _is_whois_query(text: str) -> Optional[str]:
    """Encoding-safe detector for queries like 'kto takoy <Imya>'.

    Important: uses only ASCII in the regex (via \\uXXXX escapes) to avoid source-encoding corruption.
    Never raises; returns extracted name or None.
    """

    try:
        s = (text or "").strip()
        if not s:
            return None

        # Search patterns (all Cyrillic characters are escaped for security)
        
        # 1. who (such|such|this) <Name?>b
        # \u043a\u0442\u043e = kto
        # eu0442eu0430eu043aeu043eeu0439 = such, eu0442eu0430eu043aeu0430eu044f = such, eu04chdeu0442eu043e = this
        pat_whois = (
            r"(?i)\b(?:\u043a\u0442\u043e)\s+"
            r"(?:\u0442\u0430\u043a\u043e\u0439|\u0442\u0430\u043a\u0430\u044f|\u044d\u0442\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        # 2. 'rasskazhi pro <Name?>'
        # \u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438 = rasskazhi, \u043f\u0440\u043e = pro
        pat_tell = (
            r"(?i)\b(?:\u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438)\s+(?:\u043f\u0440\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        # 3. what (you) know about <Name?>b
        # eu0447eu0442eu043e = what, eu0437eu04zdeu0430eu0435eu0448eu044k = you know, eu043e = oh, eu043eeu0431 = about
        pat_know = (
            r"(?i)\b(?:\u0447\u0442\u043e)\s+(?:.*\s+)?(?:\u0437\u043d\u0430\u0435\u0448\u044c)\s+(?:\u043e|\u043e\u0431)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        # Consistently checks all patterns
        for pat in [pat_whois, pat_tell, pat_know]:
            m = re.search(pat, s)
            if m:
                name = m.group(1).strip()
                # We remove the question mark if it is captured
                if name.endswith('?'):
                    name = name[:-1].strip()
                return name

        return None
    except Exception:
        # Silent return in case of any parsing error
        return None

import re
from typing import Optional

def _is_whois_query(text: str) -> Optional[str]:
    """Detektor zaprosov o lichnostyakh (Whois-intent).
    Izvlekaet imya iz fraz tipa 'kto takoy...', 'rasskazhi pro...' or 'chto znaesh o...'.
    
    Ispolzuet ASCII-eskeypy dlya kirillitsy, chtoby izbezhat problem s kodirovkoy iskhodnogo koda."""
    try:
        s = (text or "").strip()
        if not s:
            return None

        # 1. Pattern: who (such|such|this) <Name>b
        # \u043a\u0442\u043e = kto; \u0442\u0430\u043a\u043e\u0439 = takoy...
        pat_whois = (
            r"(?i)\b(?:\u043a\u0442\u043e)\s+"
            r"(?:\u0442\u0430\u043a\u043e\u0439|\u0442\u0430\u043a\u0430\u044f|\u044d\u0442\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        # 2. Pattern: 'rasskazhi pro <Name>'
        # \u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438 = rasskazhi, \u043f\u0440\u043e = pro
        pat_tell = (
            r"(?i)\b(?:\u0440\u0430\u0441\u0441\u043a\u0430\u0436\u0438)\s+(?:\u043f\u0440\u043e)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        # 3. Pattern: what do you know about <Name>
        # eu0447eu0442eu043e = what, eu0437eu04zdeu0430eu0435eu0448eu044k = you know, eu043e = oh...
        pat_know = (
            r"(?i)\b(?:\u0447\u0442\u043e)\s+(?:.*\s+)?(?:\u0437\u043d\u0430\u0435\u0448\u044c)\s+(?:\u043e|\u043e\u0431)\s+"
            r"([A-Za-z\u0400-\u04FF][A-Za-z\u0400-\u04FF\-\s]{1,40})\??\b"
        )

        # Perebor patternov
        for pat in [pat_whois, pat_tell, pat_know]:
            m = re.search(pat, s)
            if m:
                # Extraction and Normalization
                name = (m.group(1) or "").strip()
                name = re.sub(r"\s{2,}", " ", name)
                
                # The name must be meaningful (minimum 2 characters)
                return name if len(name) >= 2 else None

        return None
    except Exception:
        return None

# --- 7) PATHS (fix %ESTER_HOME% expansion robustly) ---
def _resolve_ester_home() -> str:
    """Nadezhnoe opredelenie rabochey direktorii.
    Ierarkhiya poiska: 
    1. Peremennaya okruzheniya ESTER_HOME.
    2. Papka.ester v domashney direktorii polzovatelya.
    3. Papka .ester v tekuschem rabochem kataloge (fallback)."""
    # 1. Trying to get the path from an environment variable
    h = os.getenv("ESTER_HOME", "").strip()

    # 2. Define the default path if the variable is not set
    if not h:
        try:
            # Path ~/.ester (standard for Young/MacOS and Windows)
            h = str(Path.home() / ".ester")
        except Exception:
            # If access to the home folder is restricted, uses the current directory
            h = str(Path.cwd() / ".ester")

    # 3. Expanding environment variables (ZZF0ZZAR% or $VAR) and the ~ symbol (home folder)
    expanded_path = os.path.expandvars(os.path.expanduser(h))
    
    # 4. Conversion to absolute path and normalization (symbolic link resolution)
    final_path = Path(expanded_path).resolve()

    # 5. Guaranteed creation of directories (including parent ones) if there are none
    try:
        final_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        # If it is impossible to create a folder (permission error), continue
        # but logging or writing to the database may throw an error later.
        pass

    return str(final_path)

ESTER_HOME = _resolve_ester_home()
os.environ["ESTER_HOME"] = ESTER_HOME

# --- LEGACY FILE MAPPING (Connecting your old archives) ---

# Your original path map
LEGACY_FILES_MAP = [
    ("data/passport/clean_memory.jsonl", "global_fact"),
    ("data/mem/docs.jsonl", "global_doc"),
    ("data/passport/log.jsonl", "global_log"),
    ("history_ester_node_primary.jsonl", "global_history"),
    ("state/dialog_OWNER.jsonl", "dialog_owner"),
    ("state/dialog_Ester.jsonl", "dialog_self"),
]

def _load_jsonl_legacy(file_path: str) -> list:
    """Safely reads a JSN file and returns a list of objects.
    Resistant to encoding errors and common strings."""
    results = []
    # Specifies the full path relative to Esther's home folder
    base_dir = Path(_resolve_ester_home())
    full_path = base_dir / file_path

    if not full_path.exists():
        logging.info(f"[Legacy] Fayl ne nayden: {file_path}. Propuskaem.")
        return results

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        logging.info(f"yuLegatsosch Loaded ZZF0Z records from ZZF1ZZ.")
    except Exception as e:
        logging.error(f"yuLegatsosch Error when reading ZZF0Z: ZZF1ZZ")
    
    return results

def init_legacy_memory_sync() -> Dict[str, list]:
    """It goes through the entire LEGACY_FILES_MAP card and loads data into memory.
    This is the awakening of the old personality at the start of a new core."""
    legacy_storage = {}
    
    for file_path, category in LEGACY_FILES_MAP:
        logging.info(f"[Legacy] Sinkhronizatsiya kategorii: {category}...")
        data = _load_jsonl_legacy(file_path)
        legacy_storage[category] = data
        
    return legacy_storage

from pathlib import Path

# --- INFRASTRUKTURA PUTEY I PERSISTENTNOSTI ---

# 1. Setting up the path for ChromaDB
raw_chroma = (os.environ.get("CHROMA_PERSIST_DIR") or "").strip()
if not raw_chroma:
    # Using Path for cross-platform compatibility
    raw_chroma = str(Path(ESTER_HOME) / "vstore" / "chroma")

# Expanding system variables and getting absolute path
try:
    VECTOR_DB_PATH = str(Path(os.path.expandvars(os.path.expanduser(raw_chroma))).resolve())
except Exception:
    VECTOR_DB_PATH = raw_chroma

# 2. Telegram Inbox (incoming data)
PERMANENT_INBOX = str(Path(ESTER_HOME) / "data" / "ingest" / "telegram")

# 3. Semantic and operational memory files
FACTS_FILE = os.path.join("data", "user_facts.json")
DAILY_LOG_FILE = os.path.join("data", "daily_contacts.json")
MEMORY_FILE = f"history_{NODE_IDENTITY}.jsonl"

# --- Registers (persistent, not through LLM memory) ---
# Fixed: CONTACTS_FILE and PEOPLE_FILE are external directories
CONTACTS_FILE = os.getenv("ESTER_CONTACTS_FILE", os.path.join("data", "contacts_book.json"))
PEOPLE_FILE = os.getenv("ESTER_PEOPLE_FILE", os.path.join("data", "people_registry.json"))

# 4. Guaranteed creation of all necessary directories
required_folders = [
    PERMANENT_INBOX,
    os.path.dirname(VECTOR_DB_PATH),
    "data",
    os.path.dirname(CONTACTS_FILE),
    os.path.dirname(PEOPLE_FILE)
]

for folder in required_folders:
    if folder: # Checking for an empty path
        os.makedirs(folder, exist_ok=True)

# --- Context of the last admin chat (only for false mode again) ---
# Allows the system to know where to send the results of nightly reflections if there is no incoming trigger.
LAST_ADMIN_CHAT_KEY: Optional[Tuple[int, int]] = None  # (chat_id, user_id)


# --- ContactsBook (reestr kontaktov po Telegram user_id) ---

class ContactsBook:
    """Manages user records: user_id(str) -> ЗЗФ0З.
    Data is modified through explicit commands (/yam, /setrole), rather than through text parsing."""
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._dream_source_recent: Deque[Tuple[float, str]] = deque(
            maxlen=max(200, int(DREAM_SOURCE_RECENT_MAX) * 24)
        )
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    # Alias ​​for backwards compatibility during initialization
    def init(self, path: str) -> None:
        self.__init__(path)

    def _load(self) -> None:
        """Loading data from a JSION file with protection against empty lines."""
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    self._data = json.loads(content) if content else {}
            if not isinstance(self._data, dict):
                self._data = {}
        except Exception as e:
            logging.error(f"yuKontaktsvooksch Loading error: ЗЗФ0З")
            self._data = {}

    def _save(self) -> None:
        """Atomic saving via temporary file."""
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as e:
            logging.error(f"yuKontaktsvooksch Saving error: ЗЗФ0З")
            if os.path.exists(tmp):
                os.remove(tmp)

    def get(self, user_id: int) -> Dict[str, Any]:
        """Securely obtain a copy of a user record."""
        with self._lock:
            return dict(self._data.get(str(user_id), {}) or {})

    def set(self, user_id: int, patch: Dict[str, Any]) -> None:
        """Updating a user record with recording the time of change."""
        with self._lock:
            key = str(user_id)
            cur = dict(self._data.get(key, {}) or {})
            cur.update(patch or {})
            
            # Updating the timestamp through the system Ts or falbatsk on time.theme()
            try:
                now_fn = globals().get("_safe_now_ts", lambda: int(__import__('time').time()))
                cur["updated_at"] = int(now_fn())
            except Exception:
                cur["updated_at"] = int(__import__('time').time())
                
            self._data[key] = cur
            self._save()

    def display_name(self, user) -> str:
        """Specifies the display name. 
        Priority: display_name from the registry -> Full Name from Telegram -> Username -> bUser."""
        rec = self.get(user.id)
        dn = (rec.get("display_name") or "").strip()
        if dn:
            return dn
            
        # Formirovanie imeni iz atributov obekta polzovatelya Telegram
        parts = [getattr(user, "first_name", ""), getattr(user, "last_name", "")]
        full = " ".join([p for p in parts if p]).strip()
        
        return full or getattr(user, "username", "") or "Polzovatel"

    def address_as(self, user) -> str:
        """Defines the form of contacting the user."""
        rec = self.get(user.id)
        aa = (rec.get("address_as") or "").strip()
        if aa:
            return aa
        # Auto-contact for admin, if not set explicitly
        try:
            admin_id = str(os.getenv("ADMIN_ID", "") or "")
            if admin_id and str(user.id) == admin_id:
                pref = (os.getenv("ESTER_ADMIN_ADDRESS_AS", "") or "").strip()
                if pref:
                    return pref
                # defolt bez vysokoparnosti
                return "Vanya"
        except Exception:
            pass
        return self.display_name(user)

    def role(self, user) -> str:
        """Returns the user's role in the system."""
        rec = self.get(user.id)
        return str(rec.get("role") or "").strip()

# Initsializatsiya globalnogo obekta kontaktov
CONTACTS = ContactsBook(CONTACTS_FILE)

# --- People Registers (Directory of people: family, friends, colleagues) ---

class PeopleRegistry:
    """Register of personalities: name(str) -> ZZF0Z.
    These are NOT telegram users, but real people in the human sense."""
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def init(self, path: str) -> None:
        self.__init__(path)

    def _load(self) -> None:
        """Loading a directory with support for a nested structure."""
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    raw = json.load(f) or {}
            else:
                raw = {}

            # Supports different storage formats (direct dist or wrapper)
            if isinstance(raw, dict) and "people" in raw and isinstance(raw["people"], dict):
                self._data = raw["people"]
            elif isinstance(raw, dict):
                self._data = raw
            else:
                self._data = {}
        except Exception as e:
            logging.error(f"uPeopleRegister Loading error: ZZF0Z")
            self._data = {}

    def _save(self) -> None:
        """Atomic saving of the directory."""
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"people": self._data}, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception as e:
            logging.error(f"uPeopleRegister Saving error: ZZF0Z")

    def set_person(self, name: str, relation: str = "", notes: str = "", aliases: Optional[List[str]] = None) -> None:
        """Add or update a person's record."""
        name = (name or "").strip()
        if not name:
            return
        
        aliases = [a.strip() for a in (aliases or []) if a and a.strip()]
        
        with self._lock:
            cur = dict(self._data.get(name, {}) or {})
            if relation:
                cur["relation"] = relation
            if notes:
                cur["notes"] = notes
            if aliases:
                # Obedinyaem starye i novye aliasy bez dubley
                existing_als = cur.get("aliases") or []
                cur["aliases"] = sorted(list(set(existing_als + aliases)))
            
            cur["updated_at"] = int(_safe_now_ts())
            self._data[name] = cur
            self._save()

    def get_person(self, name: str) -> Dict[str, Any]:
        """Poisk cheloveka po osnovnomu imeni ili aliasu."""
        name = (name or "").strip()
        if not name:
            return {}
        
        # 1. Direct match by key
        if name in self._data:
            return {"name": name, **(self._data.get(name) or {})}
        
        # 2. Poisk po aliasam (bez ucheta registra)
        low = name.casefold()
        for k, v in self._data.items():
            als = [str(a).casefold() for a in (v.get("aliases") or [])]
            if low in als:
                return {"name": k, **v}
        return {}

    def list_people(self, limit: int = 50) -> List[Tuple[str, Dict[str, Any]]]:
        """Returns a sorted list of all people."""
        items = list(self._data.items())
        items.sort(key=lambda kv: kv[0].casefold())
        return items[:max(1, int(limit))]

    def _normalize_for_match(self, s: str) -> str:
        """Normalize text to find name matches."""
        s = (s or "").casefold()
        # We leave only letters (including Cyrillic) and numbers
        s = re.sub(r"[^\wa-yae]+", " ", s, flags=re.UNICODE)
        s = re.sub(r"\s{2,}", " ", s).strip()
        return f" {s} "

    def context_for_text(self, text: str, max_people: int = 6) -> str:
        """Scans incoming text for known names and aliases.
        Returns a text block to be added to the LLM context."""
        txt = self._normalize_for_match(text or "")
        if not txt or not self._data:
            return ""
        
        hits: List[str] = []
        # We check each name and alias in the text
        for name, rec in self.list_people(limit=500):
            n_norm = self._normalize_for_match(name)
            
            # Checking the base name or any of the aliases
            found = False
            if n_norm.strip() and n_norm in txt:
                found = True
            else:
                for a in (rec.get("aliases") or []):
                    a_norm = self._normalize_for_match(str(a))
                    if a_norm.strip() and a_norm in txt:
                        found = True
                        break
            
            if found:
                hits.append(name)
                if len(hits) >= max_people:
                    break
        
        if not hits:
            return ""
        
        # Generates a compact list for a prompt
        out: List[str] = []
        for nm in hits:
            r = self._data.get(nm) or {}
            rel = (r.get("relation") or "").strip()
            notes = (r.get("notes") or "").strip()
            line = f"- {nm}"
            if rel:
                line += f" — {rel}"
            if notes:
                line += f". {notes}"
            out.append(line)
            
        return "\n".join(out).strip()

# Initsializatsiya globalnogo reestra
PEOPLE = PeopleRegistry(PEOPLE_FILE)

from collections import deque

# --- Deduplication (take into account update_id and edited_message) ---

# Maximum number of stored IDs (from the environment or by default 1000)
DEDUP_MAXLEN = int(os.getenv("ESTER_DEDUP_MAXLEN", "1000"))

# Queues (deques) keep order for clearing old entries
_processed_updates: deque[int] = deque(maxlen=DEDUP_MAXLEN)
_processed_msgs: deque[str] = deque(maxlen=DEDUP_MAXLEN)

# Sets (network) provide search in O(1)
_processed_update_set: set[int] = set()
_processed_msg_set: set[str] = set()

_dedup_lock = threading.Lock()

def _dedup_key_from_update(update: Update) -> str:
    """Generates a unique key for the message.
    For edited messages, the key includes the edit timestamp."""
    msg = update.effective_message
    if not msg:
        return ""
    
    chat_id = getattr(msg.chat, "id", "nochat")
    mid = getattr(msg, "message_id", "nomid")
    edit_date = getattr(msg, "edit_date", None)
    if edit_date:
        # Key for modified message: e:chat:msg_id:timestamp
        return f"e:{chat_id}:{mid}:{int(edit_date.timestamp())}"
    
    # Key for regular message: m:chat:msg_id
    return f"m:{chat_id}:{mid}"

def seen_update_once(update: Update) -> bool:
    """Checks whether this update has been processed previously.
    Returns Troy if it is a duplicate."""
    uid = getattr(update, "update_id", None)
    key = _dedup_key_from_update(update)

    with _dedup_lock:
        # 1. Check by update_id (Telegram protocol level)
        if isinstance(uid, int) and uid in _processed_update_set:
            return True
        
        # 2. Check by content/message ID (application layer)
        if key and key in _processed_msg_set:
            return True

        # Registratsiya novogo update_id
        if isinstance(uid, int):
            if len(_processed_update_set) >= DEDUP_MAXLEN:
                # Ochistka samogo starogo elementa
                if _processed_updates:
                    old = _processed_updates.popleft()
                    _processed_update_set.discard(old)
            
            _processed_updates.append(uid)
            _processed_update_set.add(uid)

        # Registering a new message key
        if key:
            if len(_processed_msg_set) >= DEDUP_MAXLEN:
                # Clearing the oldest key
                if _processed_msgs:
                    oldk = _processed_msgs.popleft()
                    _processed_msg_set.discard(oldk)
            
            _processed_msgs.append(key)
            _processed_msg_set.add(key)

    return False

# --- Short-term memory (Short-Term Memory) ---
# Isolates the conversation context for each pair (chat + user)

_short_term_by_key: Dict[Tuple[int, int], deque] = {}
_short_term_lock = threading.Lock()

def get_short_term(chat_id: int, user_id: int) -> deque:
    """Vozvraschaet potokobezopasnuyu ochered (deque) soobscheniy dlya konkretnogo polzovatelya v konkretnom chate.
    Ispolzuet SHORT_TERM_MAXLEN dlya ogranicheniya deep pamyati."""
    key = (int(chat_id), int(user_id))
    with _short_term_lock:
        if key not in _short_term_by_key:
            # Create a new queue if the key does not exist yet
            _short_term_by_key[key] = deque(maxlen=int(os.getenv("SHORT_TERM_MAXLEN", "20")))
        return _short_term_by_key[key]

# --- Cleaning and filtering responses (Response Membership) ---

def strip_duplicate_boilerplate(text: str) -> str:
    """Removes junk phrases from the response that LLM often adds, 
    if you notice duplication of messages in history (RAG/History)."""
    if not text:
        return ""
    
    # List of regular expressions for removing template phrases
    bad_patterns = [
        r"(?im)^\s*ty\s+produbliroval[ai]?\s+ego\.?\s*$",
        r"(?im)^\s*kommentariy\s+byl\s+produblirovan\.?\s*$",
        r"(?im)^\s*ya\s+ponyala\s+tvoy\s+vopros\.\s*$",
        r"(?im)^\s*ty\s+produbliroval[ai]?\s+vopros\.?\s*$",
        r"(?im)^\s*vizhu,\s*chto\s*ty\s*produbliroval[ai]?\s*soobschenie\.?\s*$",
        r"(?im)^\s*povtoryayu\s+svoy\s+otvet[:\.]?\s*$",
        r"(?im)^\s*v\s+sootvetstvii\s+s\s+predyduschim\s+zaprosom\.?\s*$",
        r"(?im)^\s*istochniki\s*:\s*n/?a\.?\s*$",
        r"(?im)^\s*sources\s*:\s*n/?a\.?\s*$",
    ]
    
    lines = text.splitlines()
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append(ln)
            continue
        # If the line matches any of the bad patterns, we skip it
        if any(re.match(p, s) for p in bad_patterns):
            continue
        out.append(ln)
        
    return "\n".join(out).strip()

def clean_ester_response(text: str) -> str:
    """Final polishing of the response before sending it to the user."""
    # 1. Calling an external filter if it is registered (for example, through plugins)
    external_cleaner = globals().get("_clean_ester_response_external")
    if external_cleaner:
        try:
            text = external_cleaner(text)
        except Exception as e:
            logging.warning(f"[Cleaner] External cleaner failed: {e}")

    if not text:
        return ""

    # 2. Removing invisible characters (Zero Vidth Space)
    text = text.replace("\u200b", "")
    
    # 3. Normalization of line breaks (no more than three in a row)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    
    # 4. Removing technical additions and duplicate phrases
    text = strip_duplicate_boilerplate(text)
    
    return text.strip()

# --- Relationship stats (auto) ---
REL_STATS_FILE = os.getenv("ESTER_REL_STATS_FILE", os.path.join("data", "memory", "relationship_stats.json"))

def _load_rel_stats() -> Dict[str, Any]:
    try:
        if os.path.exists(REL_STATS_FILE):
            with open(REL_STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"users": {}, "edges": {}}


def _save_rel_stats(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(REL_STATS_FILE), exist_ok=True)
        tmp = REL_STATS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, REL_STATS_FILE)
    except Exception:
        pass


def _get_relationship_stats(user_id: int) -> Dict[str, Any]:
    data = _load_rel_stats()
    users = data.get("users", {}) or {}
    u = users.get(str(user_id)) or {}
    first_seen = int(u.get("first_seen") or 0)
    last_seen = int(u.get("last_seen") or 0)
    count = int(u.get("count") or 0)
    days = 0
    try:
        if first_seen and last_seen:
            days = max(1, int((last_seen - first_seen) / 86400) + 1)
    except Exception:
        days = 0
    try:
        min_days = int(os.getenv("ESTER_CLOSE_MIN_DAYS", "7") or 7)
        min_count = int(os.getenv("ESTER_CLOSE_MIN_COUNT", "20") or 20)
    except Exception:
        min_days, min_count = 7, 20
    close = (days >= min_days and count >= min_count)
    return {
        "days": days,
        "count": count,
        "close": close,
        "address_pref": (u.get("address_pref") or "").strip(),
        "address_pref_ts": int(u.get("address_pref_ts") or 0),
        "address_stick_seconds": int(u.get("address_stick_seconds") or 0),
        "ema_valence": float(u.get("ema_valence") or 0.0),
        "ema_joy": float(u.get("ema_joy") or 0.0),
        "ema_anxiety": float(u.get("ema_anxiety") or 0.0),
        "ema_anger": float(u.get("ema_anger") or 0.0),
        "last_affect": (u.get("last_affect") or ""),
        "style_hint": (u.get("style_hint") or "").strip(),
        "humor_ok": bool(u.get("humor_ok")) if "humor_ok" in u else False,
        "notes": list(u.get("notes") or []),
        "notes_summary": (u.get("notes_summary") or "").strip(),
        "notes_last_revise_ts": int(u.get("notes_last_revise_ts") or 0),
        "last_seen": int(u.get("last_seen") or 0),
        "summary_last_used_ts": int(u.get("summary_last_used_ts") or 0),
        "joy_last_used_ts": int(u.get("joy_last_used_ts") or 0),
    }


def _find_people_mentions(text: str, max_people: int = 6) -> List[str]:
    try:
        return [nm for nm, _ in PEOPLE.list_people(limit=500) if PEOPLE._normalize_for_match(nm) in PEOPLE._normalize_for_match(text or "")]
    except Exception:
        return []


def _update_relationship_stats(chat_id: int, user_id: int, user_label: str, text: str) -> None:
    data = _load_rel_stats()
    users = data.setdefault("users", {})
    edges = data.setdefault("edges", {})

    uid = str(user_id)
    now = _safe_now_ts()

    u = users.get(uid, {}) or {}
    u["label"] = str(user_label or u.get("label") or "")
    u["first_seen"] = int(u.get("first_seen") or now)
    u["last_seen"] = int(now)
    u["count"] = int(u.get("count") or 0) + 1
    chats = set(u.get("chats") or [])
    chats.add(str(chat_id))
    u["chats"] = sorted(chats)

    # Rolling affect (EMA)
    try:
        alpha = float(os.getenv("ESTER_REL_EMA_ALPHA", "0.15") or 0.15)
    except Exception:
        alpha = 0.15
    try:
        scores = analyze_emotions(text) or {}
    except Exception:
        scores = {}
    v = float(scores.get("valence") or 0.0)
    j = float(scores.get("joy") or 0.0)
    a = float(scores.get("anxiety") or 0.0)
    g = float(scores.get("anger") or 0.0)
    if "ema_valence" in u:
        u["ema_valence"] = (1 - alpha) * float(u.get("ema_valence") or 0.0) + alpha * v
        u["ema_joy"] = (1 - alpha) * float(u.get("ema_joy") or 0.0) + alpha * j
        u["ema_anxiety"] = (1 - alpha) * float(u.get("ema_anxiety") or 0.0) + alpha * a
        u["ema_anger"] = (1 - alpha) * float(u.get("ema_anger") or 0.0) + alpha * g
    else:
        u["ema_valence"] = v
        u["ema_joy"] = j
        u["ema_anxiety"] = a
        u["ema_anger"] = g
    try:
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        u["last_affect"] = ", ".join([f"{k}:{v:.2f}" for k, v in sorted_scores[:2]])
    except Exception:
        u["last_affect"] = ""

    users[uid] = u

    # People mentions → user<->person edges + person<->person edges
    names = _find_people_mentions(text, max_people=8)
    if names:
        uniq = []
        for n in names:
            if n not in uniq:
                uniq.append(n)
        # user-person edges
        for n in uniq:
            key = f"user:{uid}|person:{n}"
            e = edges.get(key, {}) or {}
            e["count"] = int(e.get("count") or 0) + 1
            e["last_seen"] = int(now)
            edges[key] = e
        # person-person edges (co-mentions)
        if len(uniq) >= 2:
            for i in range(len(uniq)):
                for j in range(i + 1, len(uniq)):
                    a, b = uniq[i], uniq[j]
                    key = f"person:{a}|person:{b}"
                    e = edges.get(key, {}) or {}
                    e["count"] = int(e.get("count") or 0) + 1
                    e["last_seen"] = int(now)
                    edges[key] = e

    _save_rel_stats(data)

    # Best-effort: mirror a compact snapshot for Ester's own reflection (rate-limited)
    try:
        last_log = int(u.get("rel_log_ts") or 0)
        min_gap = int(os.getenv("ESTER_REL_LOG_GAP_SEC", "21600") or 21600)
        if now - last_log >= min_gap:
            snap = _relationship_context_for_prompt(int(user_id), str(user_label))
            if snap:
                _mirror_background_event(
                    f"[REL_STATS] user_id={uid} {snap}",
                    "memory",
                    "rel_stats",
                )
            u["rel_log_ts"] = int(now)
            users[uid] = u
            _save_rel_stats(data)
    except Exception:
        pass

    # Personal insights (soft, humanized) based on history, not one-off signals
    try:
        ev = float(u.get("ema_valence") or 0.0)
        ej = float(u.get("ema_joy") or 0.0)
        ea = float(u.get("ema_anxiety") or 0.0)
        eg = float(u.get("ema_anger") or 0.0)

        # Determine style hint
        if ea >= 0.55 or eg >= 0.55:
            style_hint = "softer and calmer; clarify and support"
            humor_ok = False
        elif ev >= 0.60 and ej >= 0.55:
            style_hint = "maybe warmer and with a little humor"
            humor_ok = True
        elif ev <= 0.35:
            style_hint = "keep the tone neutral, no jokes"
            humor_ok = False
        else:
            style_hint = "druzhelyubno i po delu"
            humor_ok = False

        u["style_hint"] = style_hint
        u["humor_ok"] = bool(humor_ok)

        # Short personal notes (compact, humanized)
        notes = list(u.get("notes") or [])
        # Only generate notes when enough interaction accumulated
        min_cnt = int(os.getenv("ESTER_NOTE_MIN_COUNT", "12") or 12)
        if int(u.get("count") or 0) >= min_cnt:
            if ea >= 0.60:
                note = "An anxious person - it’s better to go softly, with clear steps and confidence."
            elif eg >= 0.60:
                note = "There is tension - keep a calm tone, don’t argue, clarify."
            elif ev >= 0.70 and ej >= 0.60:
                note = "Warm contact - maybe a little more warmth."
            elif ev <= 0.35:
                note = "Neytralnyy kontakt — bez familyarnosti."
            else:
                note = ""
            if note and (not notes or notes[-1] != note):
                notes.append(note)
                # keep last 5 notes
                notes = notes[-5:]
                u["notes"] = notes
                # mirror into memory for Ester reflection
                try:
                    _mirror_background_event(
                        f"[REL_NOTE] user_id={uid} {note}",
                        "memory",
                        "rel_note",
                    )
                except Exception:
                    pass
        u["notes"] = notes

        # Dynamic tuning for address stability (communication parameter)
        base_stick = int(os.getenv("ESTER_ADDRESS_STICK_SECONDS", "7200") or 7200)
        # If the relationship is stable/positive, allow longer stickiness.
        if ev >= 0.60:
            u["address_stick_seconds"] = int(base_stick * 1.2)
        elif ev <= 0.35:
            u["address_stick_seconds"] = int(base_stick * 0.8)
        else:
            u["address_stick_seconds"] = int(base_stick)

        users[uid] = u
        _save_rel_stats(data)
    except Exception:
        pass


def _heuristic_summarize_notes(notes: List[str]) -> str:
    if not notes:
        return ""
    # Keep last 3, drop duplicates, make 1 line
    uniq = []
    for n in notes:
        if n and n not in uniq:
            uniq.append(n)
    tail = uniq[-3:]
    return " | ".join(tail)


async def _revise_relationship_notes(context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    """Periodic Revision: Summarizes Esther's notes.
    Doesn't delete anything, just adds totals."""
    try:
        data = _load_rel_stats()
        users = data.get("users", {}) or {}
        if not users:
            return

        now = _safe_now_ts()
        min_gap = int(os.getenv("ESTER_REL_REVISE_GAP_SEC", "43200") or 43200)  # 12h
        for uid, u in list(users.items()):
            notes = list(u.get("notes") or [])
            if not notes:
                continue
            last_rev = int(u.get("notes_last_revise_ts") or 0)
            if now - last_rev < min_gap:
                continue

            # Try LLM summary (local), fallback to heuristic
            summary = ""
            try:
                prompt = (
                    "To summarize these notes from Esther in 1-2 short sentences,"
                    "no pathos, just communication style and nuances:"
                    + "\n".join([f"- {n}" for n in notes[-5:]])
                )
                summary = await _safe_chat(
                    "local",
                    [{"role": "system", "content": prompt}],
                    temperature=0.3,
                    max_tokens=160,
                    chat_id=None,
                )
                summary = (summary or "").strip()
            except Exception:
                summary = ""

            if not summary:
                summary = _heuristic_summarize_notes(notes)

            if summary:
                u["notes_summary"] = summary
                u["notes_last_revise_ts"] = int(now)
                users[uid] = u

                try:
                    _mirror_background_event(
                        f"[REL_NOTES_SUMMARY] user_id={uid} {summary}",
                        "memory",
                        "rel_notes_summary",
                    )
                except Exception:
                    pass

        data["users"] = users
        _save_rel_stats(data)
    except Exception:
        pass


def _relationship_context_for_prompt(user_id: int, address_as: str) -> str:
    data = _load_rel_stats()
    users = data.get("users", {}) or {}
    edges = data.get("edges", {}) or {}
    uid = str(user_id)
    u = users.get(uid) or {}
    if not u:
        return ""

    first_seen = int(u.get("first_seen") or 0)
    last_seen = int(u.get("last_seen") or 0)
    count = int(u.get("count") or 0)
    days = 0
    try:
        if first_seen and last_seen:
            days = max(1, int((last_seen - first_seen) / 86400) + 1)
    except Exception:
        days = 0

    # Close-ness heuristic
    try:
        min_days = int(os.getenv("ESTER_CLOSE_MIN_DAYS", "7") or 7)
        min_count = int(os.getenv("ESTER_CLOSE_MIN_COUNT", "20") or 20)
    except Exception:
        min_days, min_count = 7, 20
    close = (days >= min_days and count >= min_count)
    close_tag = "blizkiy" if close else "znakomyy"

    # Top people linked to this user
    links = []
    for k, v in edges.items():
        if k.startswith(f"user:{uid}|person:"):
            nm = k.split("person:", 1)[1]
            links.append((nm, int(v.get("count") or 0)))
    links.sort(key=lambda x: x[1], reverse=True)
    top_links = ", ".join([f"{n}({c})" for n, c in links[:3]]) if links else "net"

    # Strong person-person links
    rels = []
    for k, v in edges.items():
        if k.startswith("person:") and "|person:" in k:
            rels.append((k.replace("person:", ""), int(v.get("count") or 0)))
    rels.sort(key=lambda x: x[1], reverse=True)
    top_rels = ", ".join([f"{n}({c})" for n, c in rels[:2]]) if rels else "net"

    try:
        last_dt = datetime.datetime.fromtimestamp(last_seen).strftime("%Y-%m-%d")
    except Exception:
        last_dt = str(last_seen or "")

    # Humanized hints for tone based on memory
    try:
        seen_gap_days = int(max(0, (_safe_now_ts() - last_seen) / 86400)) if last_seen else 0
    except Exception:
        seen_gap_days = 0
    if close and seen_gap_days >= int(os.getenv("ESTER_LONG_GAP_DAYS", "14") or 14):
        vibe = "joyful meeting after a long break"
    elif close:
        vibe = "teplo i druzhelyubno"
    else:
        vibe = "vezhlivo i spokoyno"

    # Ester's own view based on history (EMA)
    try:
        ev = float(u.get("ema_valence") or 0.0)
        ej = float(u.get("ema_joy") or 0.0)
        ea = float(u.get("ema_anxiety") or 0.0)
        eg = float(u.get("ema_anger") or 0.0)
    except Exception:
        ev = ej = ea = eg = 0.0
    if ev >= 0.60 and ej >= 0.55:
        est_view = "simpatiya/radost"
    elif ea >= 0.55 or eg >= 0.50:
        est_view = "napryazhenie/ostorozhnost"
    elif ev >= 0.50:
        est_view = "generally positive"
    elif ev <= 0.35:
        est_view = "neytralno/sderzhanno"
    else:
        est_view = "neytralno"

    style_hint = (u.get("style_hint") or "").strip()
    humor_ok = bool(u.get("humor_ok")) if "humor_ok" in u else False
    humor_note = "yumor umesten" if humor_ok else "bez shutok"
    notes = list(u.get("notes") or [])
    notes_str = "; ".join(notes[-3:]) if notes else "net"
    notes_summary = (u.get("notes_summary") or "").strip() or "net"
    try:
        last_used = int(u.get("summary_last_used_ts") or 0)
        gap_hours = int(max(0, (_safe_now_ts() - last_used) / 3600)) if last_used else 9999
    except Exception:
        gap_hours = 9999

    return (
        f"Blizost: {close_tag}. "
        f"Communication period: ZZF0Z days, messages: ZZF1ZZ, last contact: ZZF2ZZ."
        f"Related people: ZZF0Z."
        f"Connections between people: ZZF0Z."
        f"Otsenka Ester: {est_view}. "
        f"Lichnyy vyvod: {style_hint or 'net'} ({humor_note}). "
        f"Zametki Ester: {notes_str}. "
        f"Summarizatsiya zametok: {notes_summary}. "
        f"Summation was used ZZF0Zx ago."
        f"Rekomendovannyy ton: {vibe}. "
        f"Emo-zastavka umestna: {'da' if close else 'net'}. "
        f"Radost vstrechi umestna: {'da' if (close and seen_gap_days >= int(os.getenv('ESTER_LONG_GAP_DAYS', '14') or 14)) else 'net'}."
    )

# --- Daylo log (Source of truth: “whom I spoke to today”) ---

def log_interaction(chat_id: int, user_id: int, user_label: str, text: str, message_id: Optional[int] = None) -> None:
    """Records the fact of interaction in a short-term daily log.
    Now includes an emotional vector for retrospective analysis."""
    try:
        now = _safe_now_ts()
        log_data: List[Dict[str, Any]] = []
        
        # 1. Zagruzka suschestvuyuschego loga
        if os.path.exists(DAILY_LOG_FILE):
            try:
                with open(DAILY_LOG_FILE, "r", encoding="utf-8") as f:
                    log_data = json.load(f) or []
            except (json.JSONDecodeError, ValueError):
                log_data = []

        if not isinstance(log_data, list):
            log_data = []

        # 2. Analysis of affect (our extension c = a + b)
        # We save the top 2 dominant emotions for log compactness
        affect_str = ""
        try:
            scores = analyze_emotions(text)
            # Sortiruem i berem samye yarkie signaly
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            affect_str = ", ".join([f"{k}:{v:.1f}" for k, v in sorted_scores[:2]])
        except Exception:
            affect_str = "neutral"

        # 3. Podgotovka zapisi
        preview = (text[:120] + "...") if len(text) > 120 else text
        entry = {
            "time": now,
            "time_str": time.strftime("%H:%M", time.localtime(now)),
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "user_label": str(user_label or "Polzovatel"),
            "preview": preview,
            "affect": affect_str, # Emotional trace
            "message_id": str(message_id) if message_id is not None else "",
        }

        # 4. Data update (stores the last 400 contacts per day)
        log_data.append(entry)
        log_data = log_data[-400:]

        # 5. Atomic write (protection against file corruption in case of failure)
        tmp_file = DAILY_LOG_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DAILY_LOG_FILE)

        try:
            _update_relationship_stats(chat_id, user_id, user_label, text)
        except Exception:
            pass

    except Exception as e:
        logging.error(f"yuDailoLogshch Logging error: ZZF0Z")
        return


# --- Memory facade (canonical entrypoint) ---
ESTER_MEM_FACADE = (os.getenv("ESTER_MEM_FACADE", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
ESTER_MEM_FACADE_STRICT = (os.getenv("ESTER_MEM_FACADE_STRICT", "0") or "0").strip().lower() in ("1", "true", "yes", "on")

def memory_add(kind: str, text: str, meta: Optional[Dict[str, Any]] = None):
    """
    Canonical memory entrypoint (wrapper).
    """
    try:
        from modules.memory.facade import memory_add as _mem_add  # type: ignore
        return _mem_add(kind, text, meta=meta)
    except Exception:
        return None

# --- Memory mirror (legacy) ---
def _append_clean_memory(user_text: str, assistant_text: str) -> None:
    try:
        passport_path = _passport_jsonl_path()
        Path(passport_path).parent.mkdir(parents=True, exist_ok=True)
        obj = {"ts": _safe_now_ts(), "user": user_text, "assistant": assistant_text}
        with open(passport_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.warning(f"[MEMORY] clean_memory append failed: {e}")


def _mirror_memory_record(text: str, meta: Optional[Dict[str, Any]] = None) -> None:
    if ESTER_MEM_FACADE:
        if ESTER_MEM_FACADE_STRICT:
            raise RuntimeError("[MEMORY] direct mirror blocked; use memory_add()")
        return memory_add("dialog", text, meta=meta or {})
    # legacy path (kept for fallback)
    try:
        from modules.memory import store  # type: ignore
        memory_add("dialog", text, meta=meta or {})
    except Exception:
        pass


def _mirror_background_event(text: str, source: str, kind: str) -> None:
    try:
        meta = {"source": str(source), "type": str(kind), "scope": "global", "ts": _safe_now_ts()}
        if ESTER_MEM_FACADE:
            memory_add("event", text, meta)
        else:
            _mirror_memory_record(text, meta)
    except Exception:
        pass


def mirror_interaction_memory(user_text: str, assistant_text: str, *, chat_id: int, user_id: int, user_label: str) -> None:
    if not user_text and not assistant_text:
        return
    meta = {
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "user_label": str(user_label or ""),
        "ts": _safe_now_ts(),
        "source": "telegram",
    }
    try:
        _append_clean_memory(user_text, assistant_text)
    except Exception:
        pass
    if user_text:
        _mirror_memory_record(f"U: {user_text}", meta)
    if assistant_text:
        _mirror_memory_record(f"A: {assistant_text}", meta)

def get_daily_summary(chat_id: Optional[int] = None, limit: int = 15) -> str:
    """Generates a human-readable report on today's activity.
    Takes into account filtering by chat and displays emotional coloring (Affect)."""
    if not os.path.exists(DAILY_LOG_FILE):
        return "There hasn't been anyone yet today."

    try:
        with open(DAILY_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or []
            
        if not isinstance(data, list) or not data:
            return "There hasn't been anyone yet today."

        # 1. Filtering by chat context
        filt = data
        if chat_id is not None:
            cid = str(chat_id)
            filt = [x for x in data if str(x.get("chat_id", "")) == cid]

        if not filt:
            return "There is no activity recorded in this channel today."

        # 2. Report assembly
        summary: List[str] = []
        seen = set() # To deduplicate frequent repetitions from one user
        
        # We analyze the last 200 events, moving from new to old
        for entry in reversed(filt[-200:]):
            key = (entry.get("user_id"), entry.get("preview"))
            if key in seen:
                continue
            seen.add(key)

            who = entry.get("user_label", "Polzovatel")
            when = entry.get("time_str", "??:??")
            pv = entry.get("preview", "")
            affect = entry.get("affect", "") # Our new emotional layer

            # Format the line: Time | Name yuEmotions: Text
            affect_tag = f" [{affect}]" if affect else ""
            line = f"• {when} | {who}{affect_tag}: «{pv}»"
            
            summary.append(line)
            
            # Limiting the size of the issue
            if len(summary) >= max(1, int(limit)):
                break
        
        if not summary:
            return "The magazine is empty."

        # Adds a header for solidity (Harvey Specter style)
        header = f"Activity report (Top-ZZF0Z):"
        return header + "\n".join(summary)

    except Exception as e:
        logging.error(f"yuDailoLogshch Error generating summary: ZZF0Z")
        return "An error occurred while reading the contact log."


def _tg_proactive_state_path() -> str:
    p = str(ESTER_TG_PROACTIVE_STATE_PATH or "").strip()
    if not p:
        p = os.path.join("data", "proactivity", "telegram_state.json")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    except Exception:
        pass
    return p


def _load_tg_proactive_state() -> Dict[str, Any]:
    path = _tg_proactive_state_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def _save_tg_proactive_state(state: Dict[str, Any]) -> None:
    path = _tg_proactive_state_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state or {}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _resolve_admin_chat_for_proactive() -> Optional[int]:
    global LAST_ADMIN_CHAT_KEY
    try:
        if LAST_ADMIN_CHAT_KEY and len(LAST_ADMIN_CHAT_KEY) >= 1:
            return int(LAST_ADMIN_CHAT_KEY[0])
    except Exception:
        pass
    for key in ("ADMIN_ID", "ADMIN_TG_ID"):
        try:
            raw = str(os.getenv(key, "") or "").strip()
            if raw and raw.lstrip("-").isdigit():
                return int(raw)
        except Exception:
            continue
    return None


def _is_quiet_hour(hour: int, quiet_start_h: int, quiet_end_h: int) -> bool:
    s = int(quiet_start_h) % 24
    e = int(quiet_end_h) % 24
    h = int(hour) % 24
    if s == e:
        return False
    if s < e:
        return s <= h < e
    return (h >= s) or (h < e)


def _build_daily_digest_text_24h(limit_events: int = 160) -> str:
    events: List[Dict[str, Any]] = []
    try:
        events = get_recent_activity_events(days=1, chat_id=None, limit=max(20, int(limit_events)))
    except Exception:
        events = []

    try:
        summary = get_recent_activity_summary(days=1, chat_id=None, limit=20)
    except Exception:
        summary = ""

    people_counter: Counter[str] = Counter()
    thought_lines: List[str] = []
    web_lines: List[str] = []
    activity_lines: List[str] = []

    for it in events:
        txt = str(it.get("text") or "").strip()
        if not txt:
            continue

        who = str(it.get("user_label") or it.get("user_name") or "").strip()
        if who and who.lower() not in ("memory", "chroma"):
            people_counter[who] += 1

        low = txt.lower()
        if ("[dream_result]" in low) or ("[insight]" in low) or ("dream_" in low):
            thought_lines.append(txt)
        if ("web_" in low) or ("self-research" in low) or ("http://" in low) or ("https://" in low):
            web_lines.append(txt)

        try:
            dt = datetime.datetime.fromtimestamp(float(it.get("ts") or 0)).strftime("%H:%M")
        except Exception:
            dt = "--:--"
        activity_lines.append(f"- {dt}: {truncate_text(txt.replace(chr(10), ' '), 140)}")

    people_top = [name for name, _ in people_counter.most_common(8)]
    people_block = ", ".join(people_top) if people_top else "I didn’t record any new dialogues with users."

    thought_block = "\n".join(f"- {truncate_text(x, 180)}" for x in thought_lines[:5]) or "- There are no obvious new formulations of sleep/reflection in the 24-hour log."
    web_block = "\n".join(f"- {truncate_text(x, 180)}" for x in web_lines[:5]) or "- There are no individual WEB events in the log for 24 hours."
    activity_block = "\n".join(activity_lines[:8]) or "- No new events found."
    summary_block = truncate_text(summary or "The summary is still empty.", 1200)

    return (
        "📝 Summary of the last 24 hours"
        "1) Chem zanimalas:\n"
        f"{activity_block}\n\n"
        "2) S kem obschalas:\n"
        f"{people_block}\n\n"
        "3) O chem dumala:\n"
        f"{thought_block}\n\n"
        "4) What I read/checked on the Internet:"
        f"{web_block}\n\n"
        "Kratkiy obschiy srez:\n"
        f"{summary_block}"
    ).strip()


def _presence_ping_text() -> str:
    variants = [
        "I'm in touch. How are you doing? If you want, we will analyze any problem right now.",
        "I check the channel: how are you? I can briefly help you with current affairs.",
        "I'm nearby. Would you like me to make a quick analysis of what is important now?",
        "I'm here. How's your day going? If necessary, I will get involved in the work.",
    ]
    idx = int((_safe_now_ts() // 3600) % max(1, len(variants)))
    return variants[idx]


async def _telegram_daily_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ESTER_INITIATIVE_DAILY_DIGEST:
        return
    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is None:
        return

    now_ts = _safe_now_ts()
    state = _load_tg_proactive_state()
    last_ts = float(state.get("daily_digest_ts", 0.0) or 0.0)
    if (now_ts - last_ts) < max(60, int(ESTER_TG_DAILY_DIGEST_MIN_GAP_SEC)):
        return

    try:
        hour_now = int(datetime.datetime.now().hour)
    except Exception:
        hour_now = -1
    if int(ESTER_TG_DAILY_DIGEST_HOUR) != hour_now:
        return

    text = _build_daily_digest_text_24h()
    if not text:
        return

    try:
        await context.bot.send_message(chat_id=int(chat_id), text=truncate_text(text, TG_MAX_LEN_SAFE))
        state["daily_digest_ts"] = now_ts
        state["daily_digest_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        _save_tg_proactive_state(state)
        _mirror_background_event("[TG_DAILY_DIGEST] sent", "proactivity", "daily_digest")
    except Exception as e:
        logging.warning(f"[PROACTIVE] daily digest send failed: {e}")


async def _telegram_presence_ping_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ESTER_TG_PRESENCE_ENABLED:
        return
    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is None:
        return

    try:
        h_now = int(datetime.datetime.now().hour)
    except Exception:
        h_now = 0
    if _is_quiet_hour(h_now, ESTER_TG_PRESENCE_QUIET_START_H, ESTER_TG_PRESENCE_QUIET_END_H):
        return

    now_ts = _safe_now_ts()
    state = _load_tg_proactive_state()
    last_ts = float(state.get("presence_ping_ts", 0.0) or 0.0)
    if (now_ts - last_ts) < max(60, int(ESTER_TG_PRESENCE_MIN_GAP_SEC)):
        return

    text = _presence_ping_text()
    try:
        await context.bot.send_message(chat_id=int(chat_id), text=truncate_text(text, TG_MAX_LEN_SAFE))
        state["presence_ping_ts"] = now_ts
        _save_tg_proactive_state(state)
        _mirror_background_event("[TG_PRESENCE_PING] sent", "proactivity", "presence_ping")
    except Exception as e:
        logging.warning(f"[PROACTIVE] presence ping send failed: {e}")


async def _telegram_token_cost_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ESTER_TG_TOKEN_COST_REPORT_ENABLED:
        return
    if _token_cost_report is None:
        return

    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is None:
        return

    now_ts = _safe_now_ts()
    state = _load_tg_proactive_state()
    last_ts = float(state.get("token_cost_report_ts", 0.0) or 0.0)
    if (now_ts - last_ts) < max(60, int(ESTER_TG_TOKEN_COST_REPORT_MIN_GAP_SEC)):
        return

    try:
        hour_now = int(datetime.datetime.now().hour)
    except Exception:
        hour_now = -1
    if int(ESTER_TG_TOKEN_COST_REPORT_HOUR) != hour_now:
        return

    try:
        text = _token_cost_report.build_telegram_report_text(tz_name=os.getenv("ESTER_TZ", "UTC"))
    except Exception as e:
        logging.warning(f"[PROACTIVE] token cost report build failed: {e}")
        return

    if not str(text or "").strip():
        return

    try:
        await context.bot.send_message(chat_id=int(chat_id), text=truncate_text(text, TG_MAX_LEN_SAFE))
        state["token_cost_report_ts"] = now_ts
        state["token_cost_report_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        _save_tg_proactive_state(state)
        _mirror_background_event("[TG_TOKEN_COST_REPORT] sent", "proactivity", "token_cost_report")
    except Exception as e:
        logging.warning(f"[PROACTIVE] token cost report send failed: {e}")


def _agent_swarm_owner_value() -> str:
    if ESTER_AGENT_SWARM_OWNER:
        return ESTER_AGENT_SWARM_OWNER
    for key in ("ADMIN_ID", "ADMIN_TG_ID"):
        try:
            raw = str(os.getenv(key, "") or "").strip()
            if raw and raw.lstrip("-").isdigit():
                return f"telegram_admin:{int(raw)}"
        except Exception:
            continue
    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is not None:
        return f"telegram_admin:{int(chat_id)}"
    return "ester:swarm"


def _agent_swarm_name_seed(template_id: str) -> str:
    tid = re.sub(r"[^a-zA-Z0-9_]+", "_", str(template_id or "").replace(".", "_")).strip("_")
    if not tid:
        tid = "template"
    return f"tg.swarm.{tid}"


def _ensure_template_pool(
    template_id: str,
    *,
    target: int,
    create_batch: int,
    owner: str,
    goal: str,
    name_prefix: str = "tg.swarm",
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False,
        "template_id": str(template_id or "").strip(),
        "target": int(max(0, int(target or 0))),
        "enabled_total": 0,
        "template_total": 0,
        "template_enabled_total": 0,
        "created": [],
        "errors": [],
    }
    if _agent_factory is None or _garage_templates_registry is None:
        out["error"] = "garage_unavailable"
        return out
    tid = str(template_id or "").strip()
    if not tid:
        out["error"] = "template_id_required"
        return out
    if not _template_exists(tid):
        out["error"] = "template_not_found"
        return out

    try:
        listing = _agent_factory.list_agents()
        rows = [dict(x or {}) for x in list(listing.get("agents") or []) if isinstance(x, dict)]
    except Exception as e:
        out["error"] = f"list_agents_failed:{e}"
        return out

    enabled_rows = [r for r in rows if bool(r.get("enabled", True))]
    template_rows = [r for r in rows if str(r.get("template_id") or "").strip() == tid]
    template_enabled = [r for r in template_rows if bool(r.get("enabled", True))]
    out["enabled_total"] = len(enabled_rows)
    out["template_total"] = len(template_rows)
    out["template_enabled_total"] = len(template_enabled)

    target_n = max(0, int(target or 0))
    need = max(0, target_n - len(template_enabled))
    if need <= 0:
        out["ok"] = True
        return out

    create_n = min(need, max(1, int(create_batch or 1)))
    seed = re.sub(r"[^a-zA-Z0-9_]+", "_", f"{name_prefix}.{tid}".replace(".", "_")).strip("_") or "tg_swarm"
    now_ts = int(_safe_now_ts())
    for i in range(create_n):
        name = f"{seed}.{now_ts}.{i + 1}"
        overrides = {
            "name": truncate_text(name, 96),
            "goal": truncate_text(goal, 300),
            "owner": str(owner or "ester:swarm"),
        }
        try:
            rep = _garage_templates_registry.create_agent_from_template(
                tid,
                overrides,
                dry_run=False,
            )
        except Exception as e:
            out["errors"].append({"name": name, "error": f"create_exception:{e}"})
            continue
        if bool(rep.get("ok")):
            out["created"].append(
                {
                    "agent_id": str(rep.get("agent_id") or ""),
                    "name": str(overrides.get("name") or ""),
                    "goal": str(overrides.get("goal") or ""),
                    "template_id": tid,
                }
            )
        else:
            out["errors"].append(
                {
                    "name": name,
                    "error": str(rep.get("error") or "create_failed"),
                    "template_id": tid,
                }
            )
    out["ok"] = True
    out["created_count"] = len(out["created"])
    out["errors_count"] = len(out["errors"])
    out["template_enabled_total_after"] = int(out["template_enabled_total"]) + int(out["created_count"] or 0)
    return out


def _parse_template_csv(raw: str) -> List[str]:
    out: List[str] = []
    for row in str(raw or "").split(","):
        tid = str(row or "").strip()
        if not tid or tid in out:
            continue
        if _template_exists(tid):
            out.append(tid)
    return out


def _ensure_role_template_pools() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "ok": False,
        "created": [],
        "errors": [],
        "templates": [],
    }
    if not ESTER_AGENT_ROLE_PREWARM_ENABLED:
        out["ok"] = True
        out["skipped"] = True
        out["reason"] = "prewarm_disabled"
        return out
    templates = _parse_template_csv(ESTER_AGENT_ROLE_PREWARM_TEMPLATES)
    out["templates"] = templates
    if not templates:
        out["ok"] = True
        out["skipped"] = True
        out["reason"] = "no_templates"
        return out

    owner = _agent_swarm_owner_value()
    for tid in templates:
        rep = _ensure_template_pool(
            tid,
            target=int(ESTER_AGENT_ROLE_PREWARM_TARGET),
            create_batch=int(ESTER_AGENT_ROLE_PREWARM_BATCH),
            owner=owner,
            goal=f"Maintain role pool for {tid}.",
            name_prefix="tg.rolepool",
        )
        out["created"].extend(list(rep.get("created") or []))
        out["errors"].extend(list(rep.get("errors") or []))
    out["ok"] = True
    out["created_count"] = len(out["created"])
    out["errors_count"] = len(out["errors"])
    return out


def _ensure_agent_swarm(target: Optional[int] = None) -> Dict[str, Any]:
    tid = str(ESTER_AGENT_SWARM_TEMPLATE_ID or "").strip()
    owner = _agent_swarm_owner_value()
    rep = _ensure_template_pool(
        tid,
        target=int(target if target is not None else ESTER_AGENT_SWARM_TARGET),
        create_batch=int(ESTER_AGENT_SWARM_CREATE_BATCH),
        owner=owner,
        goal=str(ESTER_AGENT_SWARM_GOAL),
        name_prefix=_agent_swarm_name_seed(tid),
    )
    rep.setdefault("template_id", tid)
    return rep


def _human_ago_short(delta_sec: int) -> str:
    sec = max(0, int(delta_sec or 0))
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m"
    if sec < 86400:
        return f"{sec // 3600}ch"
    return f"{sec // 86400}d"


def _collect_agent_swarm_metrics(window_sec: int) -> Dict[str, Any]:
    if _agent_factory is None:
        return {"ok": False, "error": "agent_factory_unavailable"}

    try:
        listing = _agent_factory.list_agents()
        agents_all = [dict(x or {}) for x in list(listing.get("agents") or []) if isinstance(x, dict)]
    except Exception as e:
        return {"ok": False, "error": f"list_agents_failed:{e}"}

    tid = str(ESTER_AGENT_SWARM_TEMPLATE_ID or "").strip()
    template_agents = [a for a in agents_all if str(a.get("template_id") or "").strip() == tid]
    enabled_agents = [a for a in template_agents if bool(a.get("enabled", True))]

    queue_items: List[Dict[str, Any]] = []
    if _agent_queue is not None:
        try:
            folded = _agent_queue.fold_state()
            queue_items = [dict(x or {}) for x in list(folded.get("items") or []) if isinstance(x, dict)]
        except Exception:
            queue_items = []

    now_ts = int(_safe_now_ts())
    cutoff_ts = now_ts - max(300, int(window_sec or 0))
    live_statuses = {"enqueued", "claimed", "running"}
    per: Dict[str, Dict[str, Any]] = {}

    for row in template_agents:
        aid = str(row.get("agent_id") or "").strip()
        if not aid:
            continue
        base_ts = int(row.get("updated_ts") or row.get("created_ts") or 0)
        per[aid] = {
            "agent_id": aid,
            "name": str(row.get("name") or aid),
            "goal": str(row.get("goal") or ""),
            "enabled": bool(row.get("enabled", True)),
            "tasks_total": 0,
            "done": 0,
            "failed": 0,
            "live": 0,
            "recent_total": 0,
            "recent_done": 0,
            "recent_failed": 0,
            "recent_live": 0,
            "last_ts": base_ts,
            "last_reason": "",
            "current_focus": "",
            "_focus_ts": 0,
        }

    for item in queue_items:
        aid = str(item.get("agent_id") or "").strip()
        if not aid or aid not in per:
            continue
        status = str(item.get("status") or "").strip().lower()
        ts = int(
            item.get("updated_ts")
            or item.get("finish_ts")
            or item.get("start_ts")
            or item.get("enqueue_ts")
            or 0
        )
        reason = str(
            item.get("reason")
            or item.get("done_reason")
            or item.get("error")
            or ""
        ).strip()

        st = per[aid]
        st["tasks_total"] = int(st.get("tasks_total") or 0) + 1
        st["last_ts"] = max(int(st.get("last_ts") or 0), ts)
        if reason and ts >= int(st.get("_focus_ts") or 0):
            st["last_reason"] = reason
            st["_focus_ts"] = ts
        if status == "done":
            st["done"] = int(st.get("done") or 0) + 1
        elif status == "failed":
            st["failed"] = int(st.get("failed") or 0) + 1
        elif status in live_statuses:
            st["live"] = int(st.get("live") or 0) + 1
            if reason and ts >= int(st.get("_focus_ts") or 0):
                st["current_focus"] = reason
                st["_focus_ts"] = ts

        if ts >= cutoff_ts:
            st["recent_total"] = int(st.get("recent_total") or 0) + 1
            if status == "done":
                st["recent_done"] = int(st.get("recent_done") or 0) + 1
            elif status == "failed":
                st["recent_failed"] = int(st.get("recent_failed") or 0) + 1
            elif status in live_statuses:
                st["recent_live"] = int(st.get("recent_live") or 0) + 1

    rows = list(per.values())
    for row in rows:
        row.pop("_focus_ts", None)
    rows.sort(
        key=lambda r: (
            -int(r.get("recent_total") or 0),
            -int(r.get("live") or 0),
            -int(r.get("tasks_total") or 0),
            str(r.get("name") or ""),
        )
    )

    return {
        "ok": True,
        "template_id": tid,
        "now_ts": now_ts,
        "window_sec": max(300, int(window_sec or 0)),
        "template_total": len(template_agents),
        "template_enabled_total": len(enabled_agents),
        "busy_agents": sum(1 for r in rows if int(r.get("live") or 0) > 0),
        "rows": rows,
        "recent_total": sum(int(r.get("recent_total") or 0) for r in rows),
        "recent_done": sum(int(r.get("recent_done") or 0) for r in rows),
        "recent_failed": sum(int(r.get("recent_failed") or 0) for r in rows),
        "recent_live": sum(int(r.get("recent_live") or 0) for r in rows),
        "done_total": sum(int(r.get("done") or 0) for r in rows),
        "failed_total": sum(int(r.get("failed") or 0) for r in rows),
        "tasks_total": sum(int(r.get("tasks_total") or 0) for r in rows),
    }


def _short_agent_id(agent_id: str) -> str:
    aid = str(agent_id or "")
    if len(aid) <= 10:
        return aid
    return aid[:6] + "…" + aid[-4:]


def _build_agent_swarm_report_text(window_sec: Optional[int] = None) -> str:
    wsec = max(300, int(window_sec if window_sec is not None else ESTER_TG_AGENT_SWARM_REPORT_MIN_GAP_SEC))
    rep = _collect_agent_swarm_metrics(window_sec=wsec)
    if not bool(rep.get("ok")):
        return f"🤖 Agent swarm report is unavailable: {rep.get('error') or 'unknown_error'}."

    now_ts = int(rep.get("now_ts") or _safe_now_ts())
    rows = list(rep.get("rows") or [])
    window_h = max(1, int(round(wsec / 3600.0)))

    text_lines = [
        "🤖 Agent Swarm Report",
        "",
        f"Template: `{rep.get('template_id')}`",
        (
            f"Swarm size: {int(rep.get('template_enabled_total') or 0)} active"
            f" out of {int(rep.get('template_total') or 0)} created."
        ),
        (
            f"For the last ~{window_h}h: events {int(rep.get('recent_total') or 0)}, "
            f"successes {int(rep.get('recent_done') or 0)}, failures {int(rep.get('recent_failed') or 0)}, "
            f"in progress {int(rep.get('recent_live') or 0)}."
        ),
        (
            f"Swarm totals: tasks {int(rep.get('tasks_total') or 0)}, "
            f"succeeded {int(rep.get('done_total') or 0)}, failed {int(rep.get('failed_total') or 0)}."
        ),
        "",
        "By agent:",
    ]

    if not rows:
        text_lines.append("- No agents have been created from this template yet.")
        return "\n".join(text_lines).strip()

    max_rows = max(3, int(ESTER_TG_AGENT_SWARM_REPORT_MAX_AGENTS))
    for row in rows[:max_rows]:
        name = str(row.get("name") or row.get("agent_id") or "agent")
        aid = _short_agent_id(str(row.get("agent_id") or ""))
        live_n = int(row.get("live") or 0)
        failed_n = int(row.get("failed") or 0)
        done_n = int(row.get("done") or 0)
        total_n = int(row.get("tasks_total") or 0)
        recent_n = int(row.get("recent_total") or 0)
        state_word = "v rabote" if live_n > 0 else ("est sboi" if failed_n > 0 else "stabilen")
        focus = str(row.get("current_focus") or row.get("last_reason") or row.get("goal") or "waiting for a new task").strip()
        focus = truncate_text(focus.replace("\n", " "), 110)
        last_ts = int(row.get("last_ts") or 0)
        ago = _human_ago_short(max(0, now_ts - last_ts)) if last_ts > 0 else "n/a"
        text_lines.append(
            f"- {name} ({aid}) - {state_word}; zadach: {total_n}, done: {done_n}, fail: {failed_n}, live: {live_n},"
            f"events outside the window: ZZF0Z, last activity: ZZF1ZZ ago."
        )
        text_lines.append(f"Now/last: ZZF0Z")

    if len(rows) > max_rows:
        text_lines.append(f"- ...and also ZZF0Z agents in the swarm.")

    return "\n".join(text_lines).strip()


async def _tg_bot_send_with_retry(bot: Any, chat_id: int, text: str, attempts: int = 4) -> bool:
    base_delay = float(os.getenv("TG_RETRY_BASE_DELAY", "0.7") or 0.7)
    for i in range(max(1, int(attempts))):
        try:
            safe_text = _tg_sanitize_text(text or "")
            if not safe_text.strip():
                return True
            await bot.send_message(chat_id=int(chat_id), text=safe_text)
            return True
        except Exception as e:
            try:
                if isinstance(e, RetryAfter):
                    await asyncio.sleep(float(e.retry_after) + 0.5)
                    continue
            except Exception:
                pass
            await asyncio.sleep(base_delay * (2 ** i))
    return False


async def _tg_send_message_chunks(bot: Any, chat_id: int, text: str, max_len: int = TG_MAX_LEN) -> bool:
    t = _tg_sanitize_text(_normalize_text(text or ""))
    if not t.strip():
        return True
    parts = _split_telegram_text(t, max_len)
    overall_ok = True
    for i, part in enumerate(parts):
        if not part:
            continue
        ok = await _tg_bot_send_with_retry(bot, int(chat_id), part, attempts=4)
        if not ok:
            fallback_parts = _split_telegram_text(part, max(800, int(max_len) // 2))
            for fp in fallback_parts:
                if not fp:
                    continue
                ok2 = await _tg_bot_send_with_retry(bot, int(chat_id), fp, attempts=2)
                if not ok2:
                    overall_ok = False
                    break
            if not overall_ok:
                break
        if i != len(parts) - 1:
            await asyncio.sleep(TG_SEND_DELAY)
    return overall_ok


async def _telegram_agent_swarm_maintain_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if (not ESTER_AGENT_SWARM_ENABLED) and (not ESTER_AGENT_ROLE_PREWARM_ENABLED):
        return
    created: List[Dict[str, Any]] = []

    if ESTER_AGENT_SWARM_ENABLED:
        rep = _ensure_agent_swarm(target=ESTER_AGENT_SWARM_TARGET)
        if not bool(rep.get("ok")):
            logging.warning(f"[AGENT_SWARM] ensure failed: {rep.get('error')}")
        else:
            created.extend([dict(x or {}) for x in list(rep.get("created") or []) if isinstance(x, dict)])
            if rep.get("created"):
                logging.info(
                    "[AGENT_SWARM] created=%s target=%s enabled=%s template=%s",
                    len(list(rep.get("created") or [])),
                    int(rep.get("target") or 0),
                    int(rep.get("template_enabled_total_after") or rep.get("template_enabled_total") or 0),
                    str(rep.get("template_id") or ""),
                )

    if ESTER_AGENT_ROLE_PREWARM_ENABLED:
        prewarm = _ensure_role_template_pools()
        if bool(prewarm.get("ok")):
            created.extend([dict(x or {}) for x in list(prewarm.get("created") or []) if isinstance(x, dict)])
        else:
            logging.warning(f"[AGENT_SWARM] role prewarm failed: {prewarm.get('error')}")

    if not created:
        return

    names = [str(x.get("name") or x.get("agent_id") or "").strip() for x in created]
    tpl_counter: Dict[str, int] = {}
    for row in created:
        tid = str(row.get("template_id") or "").strip() or "unknown"
        tpl_counter[tid] = int(tpl_counter.get(tid, 0)) + 1
    tpl_note = ", ".join(f"{k}:{v}" for k, v in sorted(tpl_counter.items()))

    _mirror_background_event(
        f"[AGENT_SWARM] created={len(created)} templates={tpl_note} names={', '.join(names[:6])}",
        "proactivity",
        "agent_swarm_created",
    )
    if not ESTER_AGENT_SWARM_NOTIFY_ON_CREATE:
        return
    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is None:
        return
    text = (
        "🤖 Pul agents expanded."
        f"Sozdano seychas: {len(created)}\n"
        f"According to templates: ZZF0Z"
        f"Novye agenty: {', '.join(truncate_text(n, 64) for n in names[:8])}"
    )
    try:
        await _tg_send_message_chunks(context.bot, int(chat_id), text, max_len=TG_MAX_LEN)
    except Exception as e:
        logging.warning(f"[AGENT_SWARM] notify failed: {e}")


async def _telegram_agent_swarm_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ESTER_TG_AGENT_SWARM_REPORT_ENABLED:
        return
    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is None:
        return

    now_ts = _safe_now_ts()
    state = _load_tg_proactive_state()
    last_ts = float(state.get("agent_swarm_report_ts", 0.0) or 0.0)
    if (now_ts - last_ts) < max(60, int(ESTER_TG_AGENT_SWARM_REPORT_MIN_GAP_SEC)):
        return

    try:
        h_now = int(datetime.datetime.now().hour)
    except Exception:
        h_now = 0
    if _is_quiet_hour(h_now, ESTER_TG_PRESENCE_QUIET_START_H, ESTER_TG_PRESENCE_QUIET_END_H):
        return

    text = _build_agent_swarm_report_text(window_sec=int(ESTER_TG_AGENT_SWARM_REPORT_MIN_GAP_SEC))
    if not str(text or "").strip():
        return

    try:
        ok = await _tg_send_message_chunks(context.bot, int(chat_id), text, max_len=TG_MAX_LEN)
        if ok:
            state["agent_swarm_report_ts"] = now_ts
            state["agent_swarm_report_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
            _save_tg_proactive_state(state)
            _mirror_background_event("[TG_AGENT_SWARM_REPORT] sent", "proactivity", "agent_swarm_report")
    except Exception as e:
        logging.warning(f"[PROACTIVE] agent swarm report send failed: {e}")


def _queue_live_count() -> int:
    return len(_agent_queue_live_snapshot())


def _agent_window_trace(event: str, **fields: Any) -> None:
    if not ESTER_AGENT_WINDOW_TRACE_ENABLED:
        return
    evt = str(event or "").strip() or "event"
    now_ts = float(_safe_now_ts())
    min_gap = max(0, int(ESTER_AGENT_WINDOW_TRACE_MIN_GAP_SEC))
    if min_gap > 0:
        try:
            state = _load_tg_proactive_state()
            bucket = state.get("agent_window_trace")
            if not isinstance(bucket, dict):
                bucket = {}
            last_ts = float(bucket.get(evt, 0.0) or 0.0)
            if (now_ts - last_ts) < float(min_gap):
                return
            bucket[evt] = now_ts
            state["agent_window_trace"] = bucket
            _save_tg_proactive_state(state)
        except Exception:
            pass
    try:
        extra = " ".join(
            f"{k}={truncate_text(str(v).replace(' ', '_'), 80)}"
            for k, v in fields.items()
        ).strip()
        if extra:
            logging.info("[AGENT_WINDOW] %s %s", evt, extra)
        else:
            logging.info("[AGENT_WINDOW] %s", evt)
    except Exception:
        pass


def _queue_has_runnable_items() -> bool:
    now_ts = int(_safe_now_ts())
    for row in _agent_queue_live_snapshot():
        status = str(row.get("status") or "").strip().lower()
        if status not in {"enqueued", "claimed", "running"}:
            continue
        if status in {"claimed", "running"}:
            return True
        not_before = int(row.get("not_before_ts") or 0)
        if now_ts >= not_before:
            return True
    return False


async def _agent_execution_window_keeper_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not ESTER_AGENT_WINDOW_AUTO_ENABLED:
        return
    if _execution_window is None:
        _agent_window_trace("skip_no_module")
        return

    live_count = _queue_live_count()
    needs_work = live_count >= int(ESTER_AGENT_WINDOW_MIN_LIVE_QUEUE)
    runnable = _queue_has_runnable_items()

    try:
        cur = _execution_window.current_window()
    except Exception as e:
        logging.warning(f"[AGENT_WINDOW] current_window failed: {e}")
        return

    open_now = bool(cur.get("open"))
    window_id = str(cur.get("window_id") or "")
    remaining = int(cur.get("remaining_sec") or 0)

    if open_now:
        if ESTER_AGENT_WINDOW_CLOSE_WHEN_IDLE and (not needs_work):
            try:
                rep = _execution_window.close_window(window_id, actor="ester:telegram_scheduler", reason="auto_idle_close")
                if bool(rep.get("ok")):
                    _agent_window_trace(
                        "close_idle",
                        window_id=window_id,
                        queue_live=int(live_count),
                        runnable=int(bool(runnable)),
                    )
                    _mirror_background_event("[AGENT_WINDOW] auto_close idle", "proactivity", "agent_window_close")
                else:
                    _agent_window_trace(
                        "close_idle_denied",
                        window_id=window_id,
                        queue_live=int(live_count),
                        error=str(rep.get("error") or ""),
                    )
            except Exception as e:
                logging.warning(f"[AGENT_WINDOW] auto close failed: {e}")
                _agent_window_trace(
                    "close_idle_failed",
                    window_id=window_id,
                    queue_live=int(live_count),
                    error=str(e),
                )
        else:
            _agent_window_trace(
                "already_open",
                window_id=window_id,
                remaining_sec=int(remaining),
                queue_live=int(live_count),
                runnable=int(bool(runnable)),
            )
        return

    if ESTER_AGENT_WINDOW_OPEN_ONLY_IF_QUEUE and (not needs_work):
        _agent_window_trace(
            "skip_no_queue",
            queue_live=int(live_count),
            min_live=int(ESTER_AGENT_WINDOW_MIN_LIVE_QUEUE),
            runnable=int(bool(runnable)),
        )
        return
    if ESTER_AGENT_WINDOW_OPEN_ONLY_IF_QUEUE and (not runnable):
        _agent_window_trace(
            "skip_no_runnable",
            queue_live=int(live_count),
            min_live=int(ESTER_AGENT_WINDOW_MIN_LIVE_QUEUE),
        )
        return

    try:
        rep = _execution_window.open_window(
            actor="ester:telegram_scheduler",
            reason=ESTER_AGENT_WINDOW_REASON,
            ttl_sec=int(ESTER_AGENT_WINDOW_TTL_SEC),
            budget_seconds=int(ESTER_AGENT_WINDOW_BUDGET_SECONDS),
            budget_energy=int(ESTER_AGENT_WINDOW_BUDGET_ENERGY),
            meta={
                "source": "telegram_scheduler",
                "auto": True,
                "live_queue": int(live_count),
            },
        )
        if bool(rep.get("ok")):
            new_wid = str(rep.get("window_id") or "")
            logging.info(
                "[AGENT_WINDOW] auto_open window_id=%s ttl=%s queue_live=%s",
                new_wid,
                int(ESTER_AGENT_WINDOW_TTL_SEC),
                int(live_count),
            )
            _agent_window_trace(
                "auto_open_ok",
                window_id=new_wid,
                ttl_sec=int(ESTER_AGENT_WINDOW_TTL_SEC),
                queue_live=int(live_count),
                runnable=int(bool(runnable)),
            )
            _mirror_background_event(
                f"[AGENT_WINDOW] auto_open ttl={int(ESTER_AGENT_WINDOW_TTL_SEC)} queue_live={int(live_count)}",
                "proactivity",
                "agent_window_open",
            )
        else:
            logging.warning(f"[AGENT_WINDOW] auto_open denied: {rep}")
            _agent_window_trace(
                "auto_open_deny",
                queue_live=int(live_count),
                runnable=int(bool(runnable)),
                error=str(rep.get("error") or ""),
            )
    except Exception as e:
        logging.warning(f"[AGENT_WINDOW] auto_open failed: {e}")
        _agent_window_trace(
            "auto_open_failed",
            queue_live=int(live_count),
            runnable=int(bool(runnable)),
            error=str(e),
        )


async def _agent_supervisor_tick_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not ESTER_AGENT_SUPERVISOR_ENABLED:
        return
    if _agent_supervisor is None:
        return
    try:
        rep = _agent_supervisor.tick_once(
            actor="ester:telegram_scheduler",
            reason=ESTER_AGENT_SUPERVISOR_REASON,
            dry_run=False,
        )
        if bool(rep.get("ran")):
            logging.info(
                "[AGENT_SUPERVISOR] ran queue_id=%s agent_id=%s run_id=%s",
                str(rep.get("queue_id") or ""),
                str(rep.get("agent_id") or ""),
                str(rep.get("run_id") or ""),
            )
            _mirror_background_event(
                f"[AGENT_SUPERVISOR] ran queue={rep.get('queue_id')} agent={rep.get('agent_id')}",
                "proactivity",
                "agent_supervisor_tick",
            )
        elif not bool(rep.get("ok")):
            logging.warning(f"[AGENT_SUPERVISOR] tick failed: {rep}")
    except Exception as e:
        logging.warning(f"[AGENT_SUPERVISOR] tick exception: {e}")


def _agent_approval_state_bucket(state: Dict[str, Any]) -> Dict[str, Any]:
    bucket = state.get("agent_approval")
    if not isinstance(bucket, dict):
        bucket = {}
    if not isinstance(bucket.get("pending_by_chat"), dict):
        bucket["pending_by_chat"] = {}
    if not isinstance(bucket.get("prompted_queue"), dict):
        bucket["prompted_queue"] = {}
    if not isinstance(bucket.get("prompted_requests"), dict):
        bucket["prompted_requests"] = {}
    state["agent_approval"] = bucket
    return bucket


def _agent_pending_get(state: Dict[str, Any], chat_id: int) -> Dict[str, Any]:
    bucket = _agent_approval_state_bucket(state)
    row = (bucket.get("pending_by_chat") or {}).get(str(int(chat_id)))
    return dict(row or {}) if isinstance(row, dict) else {}


def _agent_pending_set(state: Dict[str, Any], chat_id: int, payload: Dict[str, Any]) -> None:
    bucket = _agent_approval_state_bucket(state)
    by_chat = dict(bucket.get("pending_by_chat") or {})
    by_chat[str(int(chat_id))] = dict(payload or {})
    bucket["pending_by_chat"] = by_chat
    state["agent_approval"] = bucket


def _agent_pending_clear(state: Dict[str, Any], chat_id: int) -> None:
    bucket = _agent_approval_state_bucket(state)
    by_chat = dict(bucket.get("pending_by_chat") or {})
    by_chat.pop(str(int(chat_id)), None)
    bucket["pending_by_chat"] = by_chat
    state["agent_approval"] = bucket


def _agent_mark_prompted(state: Dict[str, Any], *, kind: str, item_id: str, ts: float) -> None:
    bucket = _agent_approval_state_bucket(state)
    key = "prompted_queue" if kind == "queue" else "prompted_requests"
    rows = dict(bucket.get(key) or {})
    rows[str(item_id or "")] = float(ts)
    if len(rows) > 5000:
        ordered = sorted(rows.items(), key=lambda kv: float(kv[1]))
        rows = dict(ordered[-2500:])
    bucket[key] = rows
    state["agent_approval"] = bucket


def _agent_recently_prompted(state: Dict[str, Any], *, kind: str, item_id: str, now_ts: float, min_gap_sec: int) -> bool:
    bucket = _agent_approval_state_bucket(state)
    key = "prompted_queue" if kind == "queue" else "prompted_requests"
    rows = dict(bucket.get(key) or {})
    last_ts = float(rows.get(str(item_id or ""), 0.0) or 0.0)
    return (now_ts - last_ts) < max(60, int(min_gap_sec))


_AGENT_CONFIRM_YES = {
    "da",
    "aga",
    "ugu",
    "yes",
    "ok",
    "okay",
    "ok",
    "okey",
    "odobryayu",
    "podtverzhdayu",
    "podtverzhdayus",
    "odobreno",
    "podtverzhdeno",
    "zapuskay",
    "sozdavay",
}

_AGENT_CONFIRM_NO = {
    "net",
    "nea",
    "no",
    "otmena",
    "otklonyayu",
    "otklonit",
    "ne odobryayu",
    "stop",
    "pozzhe",
}


def _agent_yes_no_intent(text: str) -> Optional[bool]:
    low = re.sub(r"[^\wa-yae]+", " ", str(text or "").strip().lower(), flags=re.IGNORECASE)
    low = re.sub(r"\s+", " ", low).strip()
    if not low:
        return None
    if re.search(r"\bne\s+(odobr|podtverzhd|zapusk|sozda|delay)\w*", low):
        return False
    if low in _AGENT_CONFIRM_YES:
        return True
    if low in _AGENT_CONFIRM_NO:
        return False
    tokens = [t for t in low.split(" ") if t]
    if not tokens or len(tokens) > 6:
        return None
    has_yes = any(t in _AGENT_CONFIRM_YES for t in tokens)
    has_no = any(t in _AGENT_CONFIRM_NO for t in tokens)
    if has_yes and (not has_no):
        return True
    if has_no and (not has_yes):
        return False
    return None


def _is_agent_idea_intent(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return False
    pats = [
        r"\bsozda(?:y|yte|t)\s+agent",
        r"\bsdelay\s+agent",
        r"\bnuzhen\s+agent",
        r"\bzavedi\s+agent",
        r"\bsoberi\s+agent",
        r"\bagenta?\s+dlya\b",
    ]
    return any(bool(re.search(p, low)) for p in pats)


def _extract_agent_goal_text(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    out = re.sub(r"(?i)\bsozda(?:y|yte|t)\s+agent[a-ya]*\b", "", raw)
    out = re.sub(r"(?i)\bsdelay\s+agent[a-ya]*\b", "", out)
    out = re.sub(r"(?i)\bnuzhen\s+agent[a-ya]*\b", "", out)
    out = out.strip(" \t\n\r:;,.!?-")
    if not out:
        out = raw
    return truncate_text(out, 500)


def _agent_queue_items_snapshot() -> List[Dict[str, Any]]:
    if _agent_queue is None:
        return []
    try:
        rep = _agent_queue.fold_state()
        return [dict(x or {}) for x in list(rep.get("items") or []) if isinstance(x, dict)]
    except Exception:
        return []


def _agent_queue_live_snapshot() -> List[Dict[str, Any]]:
    if _agent_queue is None:
        return []
    try:
        rep = _agent_queue.list_queue(live_only=True)
        return [dict(x or {}) for x in list(rep.get("items") or []) if isinstance(x, dict)]
    except Exception:
        return []


def _template_exists(template_id: str) -> bool:
    if _garage_templates_registry is None:
        return False
    tid = str(template_id or "").strip()
    if not tid:
        return False
    try:
        tpl = _garage_templates_registry.get_template(tid)
        return bool(isinstance(tpl, dict) and tpl)
    except Exception:
        return False


def _agent_role_hint_template(goal: str) -> str:
    low = str(goal or "").strip().lower()
    if not low:
        return ""
    hints = [
        (r"(clawbot|bezopasn|operator|podtverzhd|approval)", "clawbot.safe.v1"),
        (r"(proverk|review|revyu|qa|test|audit|lint|smoke|diagnost)", "reviewer.v1"),
        (r"(sober|build|realiz|kod|patch|fiks|pochin|artifact|sandbox)", "builder.v1"),
        (r"(initsiativ|proaktiv|napomn|follow[- ]?up|pingan|soobscheni[eya])", "initiator.v1"),
        (r"(arkhiv|pamyat|memory note|journal|konspekt|svodk)", "archivist.v1"),
        (r"(son|dream|refleks|reflection|podum|razmyshl)", "dreamer.v1"),
        (r"(execute|runner|zapusk|ispoln|vypoln)", "runner.v1"),
        (r"(plan|dekompoz|roadmap|strategy|strategy|shagi)", "planner.v1"),
    ]
    for pat, tid in hints:
        if re.search(pat, low):
            return tid
    return ""


def _agent_role_round_robin_template() -> str:
    seq = [
        "planner.v1",
        "reviewer.v1",
        "builder.v1",
        "initiator.v1",
        "archivist.v1",
        "dreamer.v1",
        "clawbot.safe.v1",
    ]
    state = _load_tg_proactive_state()
    bucket = dict(state.get("agent_role_router") or {})
    idx = int(bucket.get("rr_idx") or 0)
    tid = seq[idx % len(seq)]
    bucket["rr_idx"] = idx + 1
    bucket["updated_ts"] = int(_safe_now_ts())
    state["agent_role_router"] = bucket
    _save_tg_proactive_state(state)
    return tid


def _select_template_for_agent_goal(goal: str, route: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    route_tid = str((route or {}).get("template_id") or "").strip()
    via = "default"
    if route_tid:
        via = "template_bridge"
    template_id = route_tid or "planner.v1"

    if ESTER_AGENT_IDEA_ROLE_ROUTING_ENABLED:
        hint_tid = _agent_role_hint_template(goal)
        if hint_tid:
            template_id = hint_tid
            via = "role_hint"
        else:
            # If there are no obvious signals and the route was given by the planner, we make a soft roller rotator.
            if template_id == "planner.v1":
                template_id = _agent_role_round_robin_template()
                via = "role_round_robin"

    allocation: Dict[str, Any] = {}
    if _proactivity_role_allocator is not None:
        try:
            allocation = dict(
                _proactivity_role_allocator.allocate_for_goal(  # type: ignore[attr-defined]
                    goal,
                    fallback_template_id=template_id or "planner.v1",
                    candidate_templates=_proactivity_role_allocator.candidate_templates_for_goal(  # type: ignore[attr-defined]
                        goal,
                        fallback_template_id=template_id or "planner.v1",
                    ),
                    apply_templates=_proactivity_role_allocator.candidate_templates_for_goal(  # type: ignore[attr-defined]
                        goal,
                        fallback_template_id=template_id or "planner.v1",
                    ),
                    source="telegram_agent_idea",
                )
                or {}
            )
        except Exception:
            allocation = {}
    if bool(allocation.get("apply_template")):
        applied_template_id = str(allocation.get("applied_template_id") or "").strip()
        if applied_template_id:
            template_id = applied_template_id
            via = str(allocation.get("via") or "self_role_allocator")

    if not _template_exists(template_id):
        template_id = "planner.v1"
        via = "fallback_planner"

    return template_id, {"route_template_id": route_tid, "selected_via": via, "role_allocation": allocation}


def _agent_live_pressure_for(aid: str, queue_items: List[Dict[str, Any]], now_ts: int) -> Tuple[int, int, int]:
    live_weight = 0
    total_seen = 0
    recent_seen = 0
    for row in queue_items:
        if str(row.get("agent_id") or "").strip() != aid:
            continue
        status = str(row.get("status") or "").strip().lower()
        if status == "running":
            live_weight += 4
        elif status == "claimed":
            live_weight += 3
        elif status == "enqueued":
            live_weight += 2
        ts = int(
            row.get("updated_ts")
            or row.get("finish_ts")
            or row.get("start_ts")
            or row.get("enqueue_ts")
            or 0
        )
        if ts > 0:
            age = now_ts - ts
            if age <= 86400:
                total_seen += 1
            if age <= 21600:
                recent_seen += 1
    return live_weight, total_seen, recent_seen


def _pick_least_loaded_agent(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [dict(x or {}) for x in list(candidates or []) if isinstance(x, dict)]
    if not rows:
        return {}
    if not ESTER_AGENT_IDEA_BALANCER_ENABLED:
        return dict(rows[0])

    now_ts = int(_safe_now_ts())
    queue_items = _agent_queue_items_snapshot()
    scored: List[Tuple[int, int, int, int, str, Dict[str, Any]]] = []
    for row in rows:
        aid = str(row.get("agent_id") or "").strip()
        if not aid:
            continue
        live_w, total_seen, recent_seen = _agent_live_pressure_for(aid, queue_items, now_ts)
        created_ts = int(row.get("created_ts") or 0)
        score = (live_w * 100) + (total_seen * 10) + (recent_seen * 5)
        scored.append((score, live_w, total_seen, created_ts, aid, row))
    if not scored:
        return dict(rows[0])

    scored.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))
    best = dict(scored[0][5] or {})
    best["_balancer"] = {
        "score": int(scored[0][0]),
        "live_weight": int(scored[0][1]),
        "seen_total": int(scored[0][2]),
        "selected_at": now_ts,
    }
    return best


def _should_expand_template_pool(template_id: str, active_rows: List[Dict[str, Any]], same_tpl_rows: List[Dict[str, Any]]) -> bool:
    if not ESTER_AGENT_ROLE_POOL_ENABLED:
        return False
    tid = str(template_id or "").strip()
    if not tid:
        return False
    if len(active_rows) >= int(ESTER_AGENT_ROLE_MAX_TOTAL):
        return False
    if len(same_tpl_rows) < int(ESTER_AGENT_ROLE_TARGET_PER_TEMPLATE):
        return True
    return False


def _pick_existing_agent_by_template(template_id: str) -> Dict[str, Any]:
    if _agent_factory is None:
        return {}
    tid = str(template_id or "").strip()
    if not tid:
        return {}
    try:
        listing = _agent_factory.list_agents()
        existing = [dict(x or {}) for x in list(listing.get("agents") or []) if isinstance(x, dict)]
    except Exception:
        existing = []
    same_tpl = [
        row
        for row in existing
        if bool(row.get("enabled", True)) and str(row.get("template_id") or "").strip() == tid
    ]
    return _pick_least_loaded_agent(same_tpl)


def _next_pending_queue_approval() -> Dict[str, Any]:
    if _agent_queue is None:
        return {}
    try:
        rep = _agent_queue.list_queue(live_only=True)
    except Exception:
        return {}
    rows = [dict(x or {}) for x in list(rep.get("items") or []) if isinstance(x, dict)]
    pending = []
    for row in rows:
        status = str(row.get("status") or "")
        if status not in {"enqueued", "claimed"}:
            continue
        if not bool(row.get("requires_approval")):
            continue
        if bool(row.get("approved")):
            continue
        pending.append(row)
    if not pending:
        return {}
    pending.sort(
        key=lambda r: (
            -int(r.get("priority") or 0),
            int(r.get("enqueue_ts") or 0),
            str(r.get("queue_id") or ""),
        )
    )
    return dict(pending[0])


def _queue_plan_preview(item: Dict[str, Any]) -> str:
    plan = item.get("plan")
    steps: List[Dict[str, Any]] = []
    if isinstance(plan, dict):
        steps = [dict(x or {}) for x in list(plan.get("steps") or []) if isinstance(x, dict)]
    elif isinstance(plan, list):
        steps = [dict(x or {}) for x in list(plan or []) if isinstance(x, dict)]
    acts = []
    for row in steps[:4]:
        aid = str(row.get("action_id") or row.get("action") or "").strip()
        if aid:
            acts.append(aid)
    if not acts:
        return "shagi plana ne ukazany"
    tail = "..." if len(steps) > len(acts) else ""
    return ", ".join(acts) + tail


def _format_queue_approval_prompt(item: Dict[str, Any]) -> str:
    qid = str(item.get("queue_id") or "")
    aid = str(item.get("agent_id") or "") or "bez agent_id"
    reason = str(item.get("reason") or "").strip() or "reason ne ukazan"
    plan_preview = _queue_plan_preview(item)
    return (
        "We need your approval to launch the agent task."
        f"• queue_id: {qid}\n"
        f"• agent_id: {aid}\n"
        f"• reason: {truncate_text(reason, 180)}\n"
        f"• plan: {truncate_text(plan_preview, 220)}\n\n"
        "Allow execution? The answer is short: yodayo or yonecho."
    )


def _format_create_request_prompt(req: Dict[str, Any]) -> str:
    rid = str(req.get("id") or "")
    src = str(req.get("source") or "unknown")
    template_id = str(req.get("template_id") or "")
    name = str(req.get("name") or "") or "unnamed"
    goal = str(req.get("goal") or "") or "goal not provided"
    return (
        "I want to create a new agent and ask permission."
        f"• request_id: {rid}\n"
        f"• source: {src}\n"
        f"• template: {template_id}\n"
        f"• name: {name}\n"
        f"• goal: {truncate_text(goal, 260)}\n\n"
        "Create? Answer: yodayo or yonecho."
    )


def _build_agent_idea_proposal(text: str, *, chat_id: int, user_id: int) -> Dict[str, Any]:
    if _garage_templates_registry is None:
        return {"ok": False, "error": "templates_registry_unavailable"}
    if _agent_queue is None:
        return {"ok": False, "error": "agent_queue_unavailable"}
    goal = _extract_agent_goal_text(text)
    if not goal:
        goal = "Perform the task described by the operator."

    route: Dict[str, Any] = {}
    if _proactivity_template_bridge is not None:
        try:
            route = _proactivity_template_bridge.select_template(  # type: ignore[attr-defined]
                {"title": goal, "text": goal, "source": "telegram_admin_idea"}
            ) or {}
        except Exception:
            route = {}
    template_id, route_meta = _select_template_for_agent_goal(goal, route)

    existing: List[Dict[str, Any]] = []
    if _agent_factory is not None:
        try:
            listing = _agent_factory.list_agents()
            existing = [dict(x or {}) for x in list(listing.get("agents") or []) if isinstance(x, dict)]
        except Exception:
            existing = []
    active = [row for row in existing if bool(row.get("enabled", True))]
    same_tpl = [row for row in active if str(row.get("template_id") or "").strip() == template_id]

    suggested_name = f"tg.{template_id.replace('.', '_')}.{int(chat_id)}.{int(_safe_now_ts())}"
    overrides = {
        "name": truncate_text(suggested_name, 96),
        "goal": truncate_text(goal, 300),
        "owner": f"telegram_admin:{int(user_id)}",
    }

    try:
        rendered_plan = _garage_templates_registry.render_plan(template_id, overrides)
    except Exception as e:
        return {"ok": False, "error": f"render_plan_failed:{e}"}

    operation = "create_and_enqueue"
    target_agent_id = ""
    target_agent_name = ""
    selected_existing = _pick_least_loaded_agent(same_tpl)
    if selected_existing and not _should_expand_template_pool(template_id, active_rows=active, same_tpl_rows=same_tpl):
        target_agent_id = str(selected_existing.get("agent_id") or "")
        target_agent_name = str(selected_existing.get("name") or "")
        if target_agent_id:
            operation = "enqueue_existing"

    return {
        "ok": True,
        "operation": operation,
        "template_id": template_id,
        "goal": goal,
        "overrides": overrides,
        "plan": rendered_plan,
        "target_agent_id": target_agent_id,
        "target_agent_name": target_agent_name,
        "route": route,
        "routing": {
            "selected_via": str(route_meta.get("selected_via") or ""),
            "route_template_id": str(route_meta.get("route_template_id") or ""),
            "active_total": len(active),
            "same_template_total": len(same_tpl),
            "pool_expand": bool(_should_expand_template_pool(template_id, active_rows=active, same_tpl_rows=same_tpl)),
            "balancer": dict(selected_existing.get("_balancer") or {}) if isinstance(selected_existing, dict) else {},
        },
    }


def _format_agent_idea_prompt(prop: Dict[str, Any]) -> str:
    operation = str(prop.get("operation") or "")
    template_id = str(prop.get("template_id") or "")
    goal = str(prop.get("goal") or "")
    plan_preview = _queue_plan_preview({"plan": prop.get("plan")})
    routing = dict(prop.get("routing") or {})
    via = str(routing.get("selected_via") or "").strip()
    via_note = f"\n• route: {via}" if via else ""
    if operation == "enqueue_existing":
        aid = str(prop.get("target_agent_id") or "")
        aname = str(prop.get("target_agent_name") or "")
        bal = dict(routing.get("balancer") or {})
        bal_note = ""
        if bal:
            bal_note = (
                f"\n• balansirovka: score={int(bal.get('score') or 0)} "
                f"(live={int(bal.get('live_weight') or 0)}, seen={int(bal.get('seen_total') or 0)})"
            )
        return (
            "I accepted the idea. A suitable agent already exists; there is no need to create a new one."
            f"• template: {template_id}\n"
            f"• agent: {aname or aid} ({aid})\n"
            f"• tsel: {truncate_text(goal, 220)}\n"
            f"• shagi: {truncate_text(plan_preview, 220)}\n\n"
            f"{via_note}{bal_note}\n"
            "Give this agent a task now? Answer: yodayo or yonecho."
        )
    return (
        "I accepted the idea. It is better to create a new agent for this."
        f"• template: {template_id}\n"
        f"• imya: {str((prop.get('overrides') or {}).get('name') or '')}\n"
        f"• tsel: {truncate_text(goal, 220)}\n"
        f"• shagi: {truncate_text(plan_preview, 220)}\n\n"
        f"{via_note}\n"
        "Create an agent and assign a task? Answer: yodayo or yonecho."
    )


def _execute_agent_idea_proposal(prop: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    if _agent_queue is None or _garage_templates_registry is None:
        return {"ok": False, "error": "garage_unavailable"}
    operation = str(prop.get("operation") or "create_and_enqueue")
    template_id = str(prop.get("template_id") or "planner.v1")
    overrides = dict(prop.get("overrides") or {})
    queue_actor = str(actor or "ester:tg_admin")

    if operation == "enqueue_existing":
        agent_id = str(prop.get("target_agent_id") or "").strip()
        if not agent_id:
            fallback = _pick_existing_agent_by_template(template_id)
            agent_id = str(fallback.get("agent_id") or "").strip()
            if not agent_id:
                return {"ok": False, "error": "target_agent_missing"}
        plan_payload = prop.get("plan")
        qrep = _agent_queue.enqueue(
            plan_payload,
            agent_id=agent_id,
            actor=queue_actor,
            reason=f"telegram_agent_idea:{template_id}",
        )
        return {
            "ok": bool(qrep.get("ok")),
            "operation": operation,
            "agent_id": agent_id,
            "queue": qrep,
            "error": str(qrep.get("error") or ""),
        }

    create_rep = _garage_templates_registry.create_agent_from_template(
        template_id,
        overrides,
        dry_run=False,
    )
    if not bool(create_rep.get("ok")):
        return {"ok": False, "operation": operation, "error": str(create_rep.get("error") or "create_failed"), "create": create_rep}

    agent_id = str(create_rep.get("agent_id") or "")
    if not ESTER_AGENT_IDEA_AUTO_ENQUEUE:
        return {"ok": True, "operation": "create_only", "agent_id": agent_id, "create": create_rep}

    plan_payload = create_rep.get("plan")
    if not isinstance(plan_payload, dict):
        try:
            plan_payload = _garage_templates_registry.render_plan(template_id, overrides)
        except Exception:
            plan_payload = {}
    qrep = _agent_queue.enqueue(
        plan_payload,
        agent_id=agent_id,
        actor=queue_actor,
        reason=f"telegram_agent_idea:{template_id}",
    )
    return {
        "ok": bool(qrep.get("ok")),
        "operation": operation,
        "agent_id": agent_id,
        "create": create_rep,
        "queue": qrep,
        "error": str(qrep.get("error") or ""),
    }


def _resolve_agent_create_request(request_id: str, *, approve: bool, actor: str) -> Dict[str, Any]:
    if _agent_create_approval is None:
        return {"ok": False, "error": "agent_create_approval_unavailable"}
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "request_id_required"}
    req_rep = _agent_create_approval.get_request(rid)
    if not bool(req_rep.get("ok")):
        return {"ok": False, "error": str(req_rep.get("error") or "request_not_found")}
    req = dict(req_rep.get("request") or {})

    if not approve:
        deny_rep = _agent_create_approval.deny(rid, actor=actor, note="telegram_no")
        return {"ok": bool(deny_rep.get("ok")), "status": "denied", "request": dict(deny_rep.get("request") or req)}

    ap_rep = _agent_create_approval.approve(rid, actor=actor, note="telegram_yes")
    if not bool(ap_rep.get("ok")):
        return {"ok": False, "error": str(ap_rep.get("error") or "approve_failed"), "request": dict(ap_rep.get("request") or req)}
    req_now = dict(ap_rep.get("request") or req)

    if _garage_templates_registry is None:
        _agent_create_approval.fail(rid, actor=actor, error="templates_registry_unavailable", note="approval_granted_but_create_failed")
        return {"ok": False, "error": "templates_registry_unavailable", "request": req_now}

    template_id = str(req_now.get("template_id") or "")
    overrides = dict(req_now.get("overrides") or {})
    create_rep = _garage_templates_registry.create_agent_from_template(template_id, overrides, dry_run=False)
    if not bool(create_rep.get("ok")):
        _agent_create_approval.fail(
            rid,
            actor=actor,
            error=str(create_rep.get("error") or "create_failed"),
            note=str(create_rep.get("detail") or ""),
        )
        return {"ok": False, "error": str(create_rep.get("error") or "create_failed"), "create": create_rep, "request": req_now}

    agent_id = str(create_rep.get("agent_id") or "")
    _agent_create_approval.complete(rid, actor=actor, agent_id=agent_id, note="created_via_telegram_approval")
    return {"ok": True, "status": "done", "agent_id": agent_id, "create": create_rep, "request": req_now}


async def _handle_agent_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    del context
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not msg or not user or not chat:
        return False
    if not _is_admin_user(user.id):
        return False

    state = _load_tg_proactive_state()
    pending = _agent_pending_get(state, int(chat.id))
    yn = _agent_yes_no_intent(text)

    if pending and yn is not None:
        kind = str(pending.get("kind") or "")
        actor = f"telegram_admin:{int(user.id)}"
        if kind == "queue_approval":
            qid = str(pending.get("queue_id") or "")
            if _agent_queue is None:
                await msg.reply_text("I cannot process queue approval: the queue module is not available.")
            elif yn:
                rep = _agent_queue.approve(qid, actor=actor, reason="telegram_yes")
                if bool(rep.get("ok")):
                    await msg.reply_text(f"Approved. cueue_id=ZZF0Z can now be executed.")
                else:
                    await msg.reply_text(f"Failed to approve cueue_id=ZZF0Z: ZZF1ZZ")
            else:
                rep = _agent_queue.cancel(qid, actor=actor, reason="telegram_no")
                if bool(rep.get("ok")):
                    await msg.reply_text(f"Otkloneno. queue_id={qid} otmenena.")
                else:
                    await msg.reply_text(f"Failed to reject cueue_id=ZZF0Z: ZZF1ZZ")
            _agent_pending_clear(state, int(chat.id))
            _save_tg_proactive_state(state)
            return True

        if kind == "agent_create_request":
            rid = str(pending.get("request_id") or "")
            rep = _resolve_agent_create_request(rid, approve=bool(yn), actor=actor)
            if not yn:
                if bool(rep.get("ok")):
                    await msg.reply_text(f"The request to create an agent was rejected. register_id=ZZF0Z.")
                else:
                    await msg.reply_text(f"Failed to reject request_id=ZZF0Z: ZZF1ZZ")
            else:
                if bool(rep.get("ok")):
                    await msg.reply_text(
                        f"Agent sozdan. request_id={rid}, agent_id={rep.get('agent_id') or 'unknown'}."
                    )
                else:
                    await msg.reply_text(f"Failed to create agent by register_id=ZZF0Z: ZZF1ZZ")
            _agent_pending_clear(state, int(chat.id))
            _save_tg_proactive_state(state)
            return True

        if kind == "agent_idea":
            if not yn:
                await msg.reply_text("Accepted. I canceled the idea for an agent and didn’t launch anything.")
                _agent_pending_clear(state, int(chat.id))
                _save_tg_proactive_state(state)
                return True
            proposal = dict(pending.get("proposal") or {})
            rep = _execute_agent_idea_proposal(proposal, actor=actor)
            if bool(rep.get("ok")):
                queue_id = str((rep.get("queue") or {}).get("queue_id") or "")
                status_note = f", queue_id={queue_id}" if queue_id else ""
                await msg.reply_text(
                    f"Sdelano: operation={rep.get('operation')} agent_id={rep.get('agent_id')}{status_note}."
                )
            else:
                await msg.reply_text(f"Failed to execute idea on agent: ZZF0Z")
            _agent_pending_clear(state, int(chat.id))
            _save_tg_proactive_state(state)
            return True

    if ESTER_AGENT_IDEA_ENABLED and _is_agent_idea_intent(text):
        proposal = _build_agent_idea_proposal(text, chat_id=int(chat.id), user_id=int(user.id))
        if not bool(proposal.get("ok")):
            await msg.reply_text(f"I can’t prepare an agent yet: ZZF0Z")
            return True
        _agent_pending_set(
            state,
            int(chat.id),
            {
                "kind": "agent_idea",
                "created_ts": _safe_now_ts(),
                "proposal": proposal,
            },
        )
        _save_tg_proactive_state(state)
        await msg.reply_text(truncate_text(_format_agent_idea_prompt(proposal), TG_MAX_LEN_SAFE))
        return True

    return False


async def _telegram_agent_approval_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ESTER_AGENT_TG_APPROVAL_ENABLED:
        return
    chat_id = _resolve_admin_chat_for_proactive()
    if chat_id is None:
        return
    now_ts = _safe_now_ts()
    state = _load_tg_proactive_state()

    # We are not bombarded with new approvals while we are already waiting for an answer in this chat.
    if _agent_pending_get(state, int(chat_id)):
        return

    # 1) First, requests to create an agent from an autonomous loop.
    if _agent_create_approval is not None:
        try:
            pending_rep = _agent_create_approval.list_pending(limit=20)
            pending_items = [dict(x or {}) for x in list(pending_rep.get("items") or []) if isinstance(x, dict)]
        except Exception:
            pending_items = []
        for req in pending_items:
            rid = str(req.get("id") or "").strip()
            if not rid:
                continue
            if _agent_recently_prompted(
                state,
                kind="request",
                item_id=rid,
                now_ts=now_ts,
                min_gap_sec=ESTER_AGENT_TG_APPROVAL_MIN_GAP_SEC,
            ):
                continue
            text = _format_create_request_prompt(req)
            try:
                await context.bot.send_message(chat_id=int(chat_id), text=truncate_text(text, TG_MAX_LEN_SAFE))
            except Exception as e:
                logging.warning(f"[AGENT_APPROVAL] request prompt send failed: {e}")
                return
            _agent_pending_set(
                state,
                int(chat_id),
                {
                    "kind": "agent_create_request",
                    "request_id": rid,
                    "created_ts": now_ts,
                },
            )
            _agent_mark_prompted(state, kind="request", item_id=rid, ts=now_ts)
            _save_tg_proactive_state(state)
            _mirror_background_event(
                f"[TG_AGENT_APPROVAL_REQUEST] request_id={rid}",
                "proactivity",
                "agent_create_approval_request",
            )
            return

    # 2) Zatem queue items, trebuyuschie approve.
    item = _next_pending_queue_approval()
    if not item:
        return
    qid = str(item.get("queue_id") or "").strip()
    if not qid:
        return
    if _agent_recently_prompted(
        state,
        kind="queue",
        item_id=qid,
        now_ts=now_ts,
        min_gap_sec=ESTER_AGENT_TG_APPROVAL_MIN_GAP_SEC,
    ):
        return
    text = _format_queue_approval_prompt(item)
    try:
        await context.bot.send_message(chat_id=int(chat_id), text=truncate_text(text, TG_MAX_LEN_SAFE))
    except Exception as e:
        logging.warning(f"[AGENT_APPROVAL] queue prompt send failed: {e}")
        return
    _agent_pending_set(
        state,
        int(chat_id),
        {
            "kind": "queue_approval",
            "queue_id": qid,
            "created_ts": now_ts,
        },
    )
    _agent_mark_prompted(state, kind="queue", item_id=qid, ts=now_ts)
    _save_tg_proactive_state(state)
    _mirror_background_event(
        f"[TG_AGENT_APPROVAL_QUEUE] queue_id={qid}",
        "proactivity",
        "agent_queue_approval_request",
    )

# --- Web evidence (Autonomous Curiosity) ---
# Explicit BRIDGE: c=a+b -> user request (a) + web factcheck (c) => verifiable response (c)
# SKRYTYE MOSTY:
#   - Ashby: reguisite cook - external search is activated only when the desired “diversity” is required (not always)
#   - Carpet&Thomas: channel limitation - we save requests, cut the length, do not waste the network without reason
# EARTHLY Paragraph (engineering/anatomy): how breathing is not a constant “hyperfan”, but only inhales when
# there really isn’t enough oxygen (confusion/interest) or when given a direct URL.


def _format_web_evidence_fallback(results: object, max_chars: int = 6000) -> str:
    """Best-effort formatter for heterogeneous web-search outputs.

    Supports:
      - list[dict] with keys: title/snippet/url/href/link/body/text/description
      - dict with 'items'/'results' arrays
      - list[str]"""
    try:
        items = None
        if isinstance(results, dict):
            items = results.get("items") or results.get("results") or results.get("data")
        elif isinstance(results, list):
            items = results
        else:
            items = None

        if not items:
            return ""

        out_lines = []
        for it in items[:12]:
            if isinstance(it, str):
                s = it.strip()
                if s:
                    out_lines.append(f"- {s}")
                continue

            if isinstance(it, dict):
                title = str(it.get("title") or it.get("name") or "").strip()
                snippet = str(
                    it.get("snippet")
                    or it.get("body")
                    or it.get("text")
                    or it.get("description")
                    or ""
                ).strip()
                url = str(it.get("url") or it.get("link") or it.get("href") or "").strip()

                if title and snippet:
                    line = f"- {title}: {snippet}"
                elif title:
                    line = f"- {title}"
                elif snippet:
                    line = f"- {snippet}"
                else:
                    line = f"- {str(it).strip()}"

                if url:
                    line += f" ({url})"

                out_lines.append(line.strip())
                continue

            # unknown type
            out_lines.append(f"- {str(it).strip()}")

        txt = "\n".join([x for x in out_lines if x]).strip()
        if max_chars and len(txt) > max_chars:
            txt = txt[:max_chars]
        return txt
    except Exception:
        return ""


def get_web_evidence(query: str, max_results: int = 3, force_curiosity: bool = False) -> str:
    """Avtonomnyy sbor web-faktov.
    Ester sama reshaet, nuzhno li ey 'vyglyanut vovne', osnovyvayas na neopredelennosti zadachi.
    Vozvraschaet stroku vida: "[WEB_EVIDENCE]: ...." ili ""."""

    # 1) Sistemnye predokhraniteli (Closed Box / politiki)
    try:
        if globals().get("CLOSED_BOX"):
            return ""
        if str(os.getenv("WEB_FACTCHECK", "")).strip().lower() == "never":
            return ""
        if not globals().get("WEB_AVAILABLE"):
            return ""
    except Exception:
        return ""

    q = (query or "").strip()
    if not q:
        return ""

    # 2) WEB_FACTS modes: never|auto|always (if the variable is higher in the config)
    #    force_curiosity=Three always turns on search (unless closed CLOSED_BOX / false)
    try:
        mode = str(globals().get("WEB_FACTCHECK", os.getenv("WEB_FACTCHECK", "auto"))).strip().lower()
    except Exception:
        mode = "auto"

    # 3) Reshenie “lezem v set ili net”
    #    - always: vsegda (krome predokhraniteley)
    #    - auto: only if there is a URL or high confusion/interest
    #    - force_curiosity: prinuditelno
    url_in_text = bool(re.search(r"(https?://\S+)", q))

    def _is_curious_auto(text: str) -> bool:
        # if analysis_emotions is missing, it doesn’t break
        try:
            scores = analyze_emotions(text)  # type: ignore
            confusion = float(scores.get("confusion", 0.0))
            interest = float(scores.get("interest", 0.0))
            # the thresholds can be easily turned
            return (confusion > 0.60) or (interest > 0.80)
        except Exception:
            return False

    if not force_curiosity:
        if mode == "never":
            return ""
        if mode != "always":
            # auto: ekonomim resurs
            if not url_in_text and not _is_curious_auto(q):
                return ""

    # 4) URL-rezhim: headlines + site:<host> perezapis
    try:
        qlow = q.lower()
        urlm = re.search(r"(https?://\S+)", q)
        if urlm:
            url0 = urlm.group(1)

            # 4.1) If they ask for headlines/news, try extract_neadlines()
            if any(k in qlow for k in ("zagolov", "novost", "headlines", "headline")):
                try:
                    from bridges.internet_access import InternetAccess  # type: ignore
                    ia = InternetAccess()
                    # limit: a little more than max_resilts, so that there is something to take away
                    heads = ia.extract_headlines(url0, limit=max(8, int(max_results) * 4))
                    if heads:
                        out = ia.format_headlines(heads, url=url0, max_chars=int(MAX_WEB_CHARS))
                        out = (out or "").strip()
                        if out:
                            return truncate_text(f"[WEB_EVIDENCE]: {out}", int(MAX_WEB_CHARS))
                except Exception:
                    pass

            # 4.2) Rewriting the request in the sieve:<nosity> ... (better than a “sheet” with a URL)
            try:
                import urllib.parse as _up
                host = (_up.urlparse(url0).hostname or "").strip()
                if host:
                    rest = re.sub(r"https?://\S+", " ", q).strip()
                    rest = re.sub(r"\s+", " ", rest).strip()
                    if rest:
                        q = f"site:{host} {rest}"
                    else:
                        # if there is nothing else, ask “current/news”
                        q = f"site:{host} aktualnoe"
            except Exception:
                pass
    except Exception:
        pass

    # 5) Osnovnoy kaskad poiska (InternetAccess)
    try:
        logging.info(f"YuVevAutonomisch Esther initiated a web check: ZZF0Z")

        from bridges.internet_access import InternetAccess  # type: ignore
        ia = InternetAccess()

        res = ia.search(q, max_results=int(max_results or 3))

        # Some older bridges.internet_access.InternetAccess versions do not implement format_evidence().
        # We keep a local fallback formatter to avoid hard-crashing WebAutonomy.
        if hasattr(ia, "format_evidence"):
            txt = ia.format_evidence(res, max_chars=int(MAX_WEB_CHARS))  # type: ignore[attr-defined]
        else:
            txt = _format_web_evidence_fallback(res, max_chars=int(MAX_WEB_CHARS))

        txt = (txt or "").strip()

        if txt:
            return truncate_text(f"[WEB_EVIDENCE]: {txt}", int(MAX_WEB_CHARS))
    except Exception as e:
        try:
            logging.warning(f"[WebAutonomy] Sboy osnovnogo poiska: {e}")
        except Exception:
            pass

    # 6) Rezervnyy kanal (DDGS)
    try:
        if "DDGS" in globals() and DDGS:
            out = []
            with DDGS() as ddgs:
                for r in ddgs.text(q, max_results=int(max_results or 3)):
                    title = (r.get("title") or "").strip()
                    body = (r.get("body") or "").strip()
                    href = (r.get("href") or "").strip()
                    if not (title or body):
                        continue
                    row = f"- {title}: {body}"
                    if href:
                        row += f" ({href})"
                    out.append(row)

            if out:
                return truncate_text("[WEB_EVIDENCE]:\n" + "\n".join(out).strip(), int(MAX_WEB_CHARS))
    except Exception:
        return ""

    return ""


async def get_web_evidence_async(query: str, max_results: int = 3, force_curiosity: bool = False) -> str:
    """Asynchronous wrapper so as not to block the pulse of the system."""
    return await asyncio.to_thread(get_web_evidence, query, max_results, force_curiosity)

# --- Smart Curiosity cooldown (intent-aware anti-spam) ---
# Explicit BRIDGE: HF-limitation -> dose the external channel (frequency/noise/cost) => sustainable intelligence
# SKRYTYE MOSTY:
#   - Ashby: allows you to cook in portions, otherwise the system becomes noise instead of variety
#   - Carpet&Thomas: channel limited -> request rate should be policy controlled
# EARTH Paragraph (engineering/anatomy):
#   It’s like the autonomic nervous system: the reflex works, but there is a “refractory period.”
#   The heart cannot beat 20 times per second. Intelligence too.

try:
    import time as _time
except Exception:
    _time = None

try:
    import hashlib as _hashlib
except Exception:
    _hashlib = None


# We store “last times” by categories/keys
_WEB_EVIDENCE_LAST_TS_BY_KEY = {}
_WEB_EVIDENCE_LAST_TS_BY_QUERY = {}


def _web_env_float(name: str, default: float) -> float:
    try:
        v = os.getenv(name, "")
        if v is None or str(v).strip() == "":
            v = globals().get(name, default)
        return float(v)
    except Exception:
        return float(default)


def _normalize_query(q: str) -> str:
    q = (q or "").strip().lower()
    q = re.sub(r"\s+", " ", q).strip()
    # we cut the “sheets” that are too long so that the keys are stable
    if len(q) > 240:
        q = q[:240]
    return q


def _fingerprint_query(q: str) -> str:
    nq = _normalize_query(q)
    if _hashlib is None:
        return nq
    return _hashlib.sha1(nq.encode("utf-8", errors="ignore")).hexdigest()


def _extract_site_host(q: str) -> str:
    """If the request is already rewritten as site:domain...
    We use domain as a “bus” of cool."""
    try:
        m = re.search(r"\bsite:([a-z0-9\.\-]+)", q.lower())
        if m:
            return (m.group(1) or "").strip()
    except Exception:
        pass
    return ""


def _detect_intent(q: str) -> str:
    """Mini-classifier intent:
    - news: news/zagolovki/segodnya/obnovleniya
    - docs: dokumentatsiya/speki/rfc/versii/repozitorii
    - general: everything else"""
    ql = (q or "").lower()

    # novosti
    if any(k in ql for k in (
        "novost", "zagolov", "headlines", "headline", "breaking", "today", "segodnya",
        "vchera", "yesterday", "update", "obnovlen"
    )):
        return "news"

    # doki/speki/tekh
    if any(k in ql for k in (
        "rfc", "spec", "specification", "docs", "documentation", "readme",
        "github", "gitlab", "pypi", "pip ", "npm ", "maven", "nuget",
        "api ", "reference", "changelog", "release", "version", "vers", "paket"
    )):
        return "docs"

    return "general"


def _cooldown_seconds_for_intent(intent: str) -> float:
    """Politika cooldown po intentu (secundy).
    Mozhno nastraivat env-peremennymi:
      WEB_CURIOSITY_COOLDOWN_DEFAULT_SEC
      WEB_CURIOSITY_COOLDOWN_NEWS_SEC
      WEB_CURIOSITY_COOLDOWN_DOCS_SEC
      WEB_CURIOSITY_SAME_QUERY_COOLDOWN_SEC"""
    default_cd = _web_env_float("WEB_CURIOSITY_COOLDOWN_DEFAULT_SEC", 90.0)
    news_cd = _web_env_float("WEB_CURIOSITY_COOLDOWN_NEWS_SEC", 45.0)
    docs_cd = _web_env_float("WEB_CURIOSITY_COOLDOWN_DOCS_SEC", 180.0)

    if intent == "news":
        return max(0.0, news_cd)
    if intent == "docs":
        return max(0.0, docs_cd)
    return max(0.0, default_cd)


def _cooldown_blocks_autonomy_smart(q: str, force_curiosity: bool) -> bool:
    """Blokiruem tolko "avtonomnye" request:
    - bez force_curiosity
    - bez yavnogo URL
    - bez rezhima WEB_FACTCHECK=always
    I do it this way:
    1) same-query guard (esli povtoryayut odno i to zhe)
    2) intent+host bucket guard (raznye cooldown dlya news/docs/general)"""
    global _WEB_EVIDENCE_LAST_TS_BY_KEY, _WEB_EVIDENCE_LAST_TS_BY_QUERY

    if _time is None:
        return False

    q = (q or "").strip()

    # 0) Prinuditelnyy poisk ne rezhem
    if force_curiosity:
        return False

    # 1) If the user has given a URL, this is an obvious intent, do not cut it
    try:
        if re.search(r"(https?://\S+)", q):
            return False
    except Exception:
        pass

    # 2) If the policy is “always” - we don’t cut (this is a conscious mode of constant checking)
    try:
        mode = str(globals().get("WEB_FACTCHECK", os.getenv("WEB_FACTCHECK", "auto"))).strip().lower()
        if mode == "always":
            return False
    except Exception:
        pass

    # 3) same-query guard (so as not to hammer the same thing in a row)
    same_q_cd = _web_env_float("WEB_CURIOSITY_SAME_QUERY_COOLDOWN_SEC", 25.0)
    if same_q_cd > 0.0:
        qfp = _fingerprint_query(q)
        now = _time.monotonic()
        lastq = float(_WEB_EVIDENCE_LAST_TS_BY_QUERY.get(qfp, 0.0))
        if (now - lastq) < same_q_cd:
            try:
                _mirror_background_event(
                    f"[WEB_AUTONOMY_COOLDOWN] same_query {q}",
                    "autonomy",
                    "web_cooldown",
                )
            except Exception:
                pass
            return True

    # 4) intent-aware bucket cooldown
    intent = _detect_intent(q)
    host = _extract_site_host(q)
    bucket = f"{intent}:{host}" if host else intent

    cd = _cooldown_seconds_for_intent(intent)
    if cd <= 0.0:
        # cooldown disabled
        now = _time.monotonic()
        _WEB_EVIDENCE_LAST_TS_BY_KEY[bucket] = now
        try:
            _WEB_EVIDENCE_LAST_TS_BY_QUERY[_fingerprint_query(q)] = now
        except Exception:
            pass
        return False

    now = _time.monotonic()
    lastb = float(_WEB_EVIDENCE_LAST_TS_BY_KEY.get(bucket, 0.0))
    if (now - lastb) < cd:
        try:
            _mirror_background_event(
                f"[WEB_AUTONOMY_COOLDOWN] bucket={bucket} q={q}",
                "autonomy",
                "web_cooldown",
            )
        except Exception:
            pass
        return True

    # allowed => fix times
    _WEB_EVIDENCE_LAST_TS_BY_KEY[bucket] = now
    try:
        _WEB_EVIDENCE_LAST_TS_BY_QUERY[_fingerprint_query(q)] = now
    except Exception:
        pass

    return False


# We take the “core” (so as not to recurse and break calls)
# Important: if you already had an old cold wrapper, remove it in front of this block.
_get_web_evidence_core = get_web_evidence


def get_web_evidence(query: str, max_results: int = 3, force_curiosity: bool = False) -> str:
    q = (query or "").strip()

    if _cooldown_blocks_autonomy_smart(q, force_curiosity):
        try:
            logging.info("[WebAutonomy] smart-cooldown: skipped autonomous web evidence.")
        except Exception:
            pass
        return ""

    return _get_web_evidence_core(query, max_results=max_results, force_curiosity=force_curiosity)



# === GLOBALNYY ANCHOR (DYNAMIC IDENTITY) ===
# We no longer store identity here in text. We take it from Profilea.
try:
    from modules.memory.passport import get_identity
    ANCHOR = get_identity()
    logging.info("[INIT] Identity loaded from Passport (Sovereign Mode).")
except ImportError:
    logging.warning("[INIT] Passport not found! Using fallback identity.")
    ANCHOR = "You are the configured entity from Web UI profile. (Fallback Mode)"

ESTER_CORE_SYSTEM_ANCHOR = ANCHOR

# ==============================================================================
# SISTER NODE SYNAPSE (P2P BRIDGE) — Fire-and-Forget + Backoff Retries
# ==============================================================================
flask_app = Flask(__name__)

# --- .env (safe) ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception as e:
    logging.warning(f"[env] .env not loaded: {e}")


# --- register_all (safe) ---
try:
    from modules.register_all import register_all as _register_all
    _register_all(flask_app)
    try:
        _mirror_background_event(
            "[REGISTER_ALL_OK]",
            "autoload",
            "register_all",
        )
    except Exception:
        pass
except Exception as e:
    logging.warning(f"[register_all] not active: {e}")
    try:
        _mirror_background_event(
            f"[REGISTER_ALL_FAIL] {e}",
            "autoload",
            "register_all_fail",
        )
    except Exception:
        pass


# --- after_request guard (prevent None returns) ---
def _wrap_after_request_funcs(app):
    try:
        from flask import make_response  # type: ignore
    except Exception:
        make_response = None  # type: ignore
    try:
        items = list(getattr(app, 'after_request_funcs', {}).items())
    except Exception:
        return False
    for key, funcs in items:
        wrapped = []
        for fn in funcs or []:
            def _mk(f):
                def _w(resp):
                    try:
                        out = f(resp)
                    except Exception as e:
                        try:
                            logging.warning(f"[after_request] {getattr(f, '__module__', '?')}.{getattr(f, '__name__', '?')} error: {e}")
                        except Exception:
                            pass
                        return resp
                    if out is None:
                        try:
                            logging.warning(f"[after_request] {getattr(f, '__module__', '?')}.{getattr(f, '__name__', '?')} returned None; keeping previous response")
                        except Exception:
                            pass
                        return resp if resp is not None else (make_response("Internal error (sanitized)", 500) if make_response else resp)
                    return out
                _w.__name__ = getattr(f, '__name__', 'after_wrapper')
                _w.__module__ = getattr(f, '__module__', '__wrapped__')
                return _w
            wrapped.append(_mk(fn))
        try:
            app.after_request_funcs[key] = wrapped
        except Exception:
            pass
    return True

# --- autoload (safe) ---
try:
    from modules.autoload_everything import autoload_modules

    mode = os.getenv("ESTER_AUTOLOAD_MODE", "allowlist").strip().lower()
    report = autoload_modules(
        app=flask_app,
        mode=mode,
        allowlist_path="modules/autoload_allowlist.txt",
        max_failures=int(os.getenv("ESTER_AUTOLOAD_MAX_FAIL", "50")),
        log_each=bool(int(os.getenv("ESTER_AUTOLOAD_LOG_EACH", "1"))),
    )
    logging.getLogger("run_ester_fixed").info(f"[autoload] report={report}")
    try:
        _wrap_after_request_funcs(flask_app)
    except Exception:
        pass
    try:
        _mirror_background_event(
            f"[AUTOLOAD_REPORT] {truncate_text(str(report), 2000)}",
            "autoload",
            "autoload_report",
        )
    except Exception:
        pass
except Exception as e:
    logging.warning(f"[autoload] not active: {e}")
    try:
        _mirror_background_event(
            f"[AUTOLOAD_FAIL] {e}",
            "autoload",
            "autoload_fail",
        )
    except Exception:
        pass

# --- chat_api (REST chat endpoint) ---
try:
    from modules import chat_api as _chat_api  # type: ignore
    _chat_api.register(flask_app)  # type: ignore[attr-defined]
    logging.info("[chat_api] registered /ester/chat/message and /chat/message")
except Exception as e:
    logging.warning(f"[chat_api] not active: {e}")

# ------------------------------------------------------------------------------
# Sister inbound bypass for request-guards (RBAC/before_request)
# Enable by setting: ESTER_SISTER_BYPASS_GUARDS=1
#
# EXPLICIT BRIDGE: c=a+b -> inbound(a) + token/limits(b) => safe exchange(c)
# HIDDEN BRIDGES: Ashby(variety via sister), Cover&Thomas(channel limit)
# GROUND: like a fuse in a power line — we let /sister/inbound pass, but token still protects payload.
# ------------------------------------------------------------------------------
def _bypass_before_request_for_paths(_app, _paths):
    import functools
    from flask import request

    norm = set()
    for p in (_paths or []):
        s = (p or "").strip()
        if not s:
            continue
        if not s.startswith("/"):
            s = "/" + s
        if len(s) > 1 and s.endswith("/"):
            s = s[:-1]
        norm.add(s)

    def _wrap(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                path = (request.path or "").strip()
                if len(path) > 1 and path.endswith("/"):
                    path = path[:-1]
                if path in norm:
                    return None
            except Exception:
                pass
            return fn(*args, **kwargs)
        return wrapped

    try:
        br = getattr(_app, "before_request_funcs", None)
        if not br:
            return False
        for bp, funcs in list(br.items()):
            if not funcs:
                continue
            br[bp] = [_wrap(f) for f in funcs]
        return True
    except Exception:
        return False

if str(os.getenv("ESTER_SISTER_BYPASS_GUARDS", "0")).strip().lower() in ("1", "true", "yes", "on"):
    ok = _bypass_before_request_for_paths(flask_app, {"/sister/inbound", "/sister/inbound/"})
    if ok:
        logging.warning("[SISTER] bypass guards enabled for /sister/inbound")
    else:
        logging.error("[SISTER] bypass guards failed")
SISTER_NODE_URL = os.getenv("SISTER_NODE_URL", "").strip()
SISTER_SYNC_TOKEN = os.getenv("SISTER_SYNC_TOKEN", "").strip()

def _synaps_float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except Exception:
        return float(default)


def _synaps_bool_env(name: str, default: bool = True) -> bool:
    raw = str(os.getenv(name, "1" if default else "0") or "").strip().lower()
    if raw == "":
        return bool(default)
    return raw in {"1", "true", "yes", "on", "y"}


def _synaps_listener_config():
    return _synaps_config_from_legacy_listener_values(
        node_url=SISTER_NODE_URL,
        sync_token=SISTER_SYNC_TOKEN,
        node_id=os.getenv("ESTER_NODE_ID", "ester_node"),
        timeout_sec=_synaps_float_env("SISTER_SEND_TIMEOUT_SEC", 2.0),
        opinion_timeout_sec=_synaps_float_env("SISTER_OPINION_TIMEOUT_SEC", 120.0),
        enabled=_synaps_bool_env("SYNAPS_ENABLED", True),
    )

# --- Runtime tuning (env/global) ---
SISTER_SYNC_TIMEOUT_SEC = float(os.getenv("SISTER_SYNC_TIMEOUT_SEC", "2.0"))
SISTER_SYNC_MAX_RETRIES = int(os.getenv("SISTER_SYNC_MAX_RETRIES", "6"))

# Backoff: 1s,2s,4s,8s... capped, + jitter
SISTER_SYNC_BACKOFF_BASE_SEC = float(os.getenv("SISTER_SYNC_BACKOFF_BASE_SEC", "1.0"))
SISTER_SYNC_BACKOFF_CAP_SEC  = float(os.getenv("SISTER_SYNC_BACKOFF_CAP_SEC",  "30.0"))

# Queue protestion (so that the RAM never bloats)
SISTER_SYNC_QUEUE_MAX = int(os.getenv("SISTER_SYNC_QUEUE_MAX", "128"))
SISTER_SYNC_DROP_OLD  = str(os.getenv("SISTER_SYNC_DROP_OLD", "1")).strip().lower() in ("1", "true", "yes", "on")

# =======================
# Fire-and-Forget core
# =======================
import threading
import queue
import time
import random
import heapq

_SISTER_OUTBOX = queue.Queue(maxsize=max(8, SISTER_SYNC_QUEUE_MAX))
_SISTER_DELAY_HEAP = []  # (ready_ts, seq, item)
_SISTER_HEAP_LOCK = threading.Lock()
_SISTER_STOP = threading.Event()
_SISTER_WORKER_STARTED = False
_SISTER_SEQ = 0

# Optional health/circuit breaker (soft protection against threshing)
_SISTER_DOWN_UNTIL_TS = 0.0


def _now() -> float:
    return time.monotonic()


def _backoff_delay(attempt: int) -> float:
    """
    attempt: 1..N
    delay = min(cap, base * 2^(attempt-1)) + jitter(0..20%)
    """
    base = max(0.1, float(SISTER_SYNC_BACKOFF_BASE_SEC))
    cap = max(base, float(SISTER_SYNC_BACKOFF_CAP_SEC))
    raw = min(cap, base * (2 ** max(0, attempt - 1)))
    jitter = raw * random.uniform(0.0, 0.2)
    return raw + jitter


def _schedule_retry(item: dict, attempt_next: int) -> None:
    global _SISTER_SEQ
    ready = _now() + _backoff_delay(attempt_next)

    item["attempt"] = attempt_next
    item["ready_ts"] = ready

    with _SISTER_HEAP_LOCK:
        _SISTER_SEQ += 1
        heapq.heappush(_SISTER_DELAY_HEAP, (ready, _SISTER_SEQ, item))


def _pop_due_delayed() -> dict | None:
    now = _now()
    with _SISTER_HEAP_LOCK:
        if _SISTER_DELAY_HEAP and _SISTER_DELAY_HEAP[0][0] <= now:
            _, _, item = heapq.heappop(_SISTER_DELAY_HEAP)
            return item
    return None


def _deliver_payload(payload: dict) -> bool:
    """Real delivery to sister.
    Returns Troy only at 200."""
    global _SISTER_DOWN_UNTIL_TS

    if not SISTER_NODE_URL:
        return False

    # If the sister is "lying", wait for the recovery window (soft fuse)
    if _now() < float(_SISTER_DOWN_UNTIL_TS):
        return False

    try:
        resp = requests.post(
            f"{SISTER_NODE_URL}/sister/inbound",
            json=payload,
            timeout=float(SISTER_SYNC_TIMEOUT_SEC),
        )
        if resp.status_code == 200:
            try:
                preview = str(payload.get("content", ""))[:120].replace("\n", " ")
                _mirror_background_event(
                    f"[SISTER_OUTBOX_DELIVERED] {preview}",
                    "sister_outbox",
                    "deliver_ok",
                )
            except Exception:
                pass
            return True

        logging.error(f"[SYNAPSE] Sister rejected: {resp.status_code}")
        # If the sister answers with errors - a little “cool spell”
        _SISTER_DOWN_UNTIL_TS = _now() + 3.0
        try:
            preview = str(payload.get("content", ""))[:120].replace("\n", " ")
            _mirror_background_event(
                f"[SISTER_OUTBOX_REJECTED] status={resp.status_code} {preview}",
                "sister_outbox",
                "deliver_reject",
            )
        except Exception:
            pass
        return False

    except Exception as e:
        logging.error(f"[SYNAPSE] Connection failed: {e}")
        # When there is a network failure, we also cool it a little so that the network does not thresh
        _SISTER_DOWN_UNTIL_TS = _now() + 3.0
        try:
            preview = str(payload.get("content", ""))[:120].replace("\n", " ")
            _mirror_background_event(
                f"[SISTER_OUTBOX_ERROR] {e} | {preview}",
                "sister_outbox",
                "deliver_error",
            )
        except Exception:
            pass
        return False


def _worker_loop():
    """Background worker:
    - takes tasks from the queue
    - trying to deliver
    - on fail plans retro through eap done"""
    logging.info("[SYNAPSE] Worker started (fire-and-forget).")
    try:
        _mirror_background_event(
            "[SISTER_OUTBOX_WORKER_START]",
            "sister_outbox",
            "worker_start",
        )
    except Exception:
        pass

    while not _SISTER_STOP.is_set():
        # 1) first we take those that are “ripe”
        item = _pop_due_delayed()

        # 2) if not, take it from the main queue
        if item is None:
            try:
                item = _SISTER_OUTBOX.get(timeout=0.25)
            except queue.Empty:
                continue

        if not item:
            continue

        payload = item.get("payload") or {}
        attempt = int(item.get("attempt", 1))

        ok = _deliver_payload(payload)
        if ok:
            try:
                preview = str(payload.get("content", ""))[:50].replace("\n", " ")
                logging.info(f"[SYNAPSE] Delivered (attempt={attempt}): {preview}...")
            except Exception:
                logging.info("[SYNAPSE] Delivered.")
            continue

        # failed
        if attempt < int(SISTER_SYNC_MAX_RETRIES):
            _schedule_retry(item, attempt + 1)
            try:
                logging.warning(f"[SYNAPSE] Retry scheduled (attempt={attempt + 1}).")
            except Exception:
                pass
        else:
            try:
                logging.error("[SYNAPSE] Dropped message: max retries reached.")
            except Exception:
                pass
            try:
                preview = str(payload.get("content", ""))[:120].replace("\n", " ")
                _mirror_background_event(
                    f"[SISTER_OUTBOX_DROPPED] max_retries {preview}",
                    "sister_outbox",
                    "deliver_drop",
                )
            except Exception:
                pass


def _start_sister_worker_once():
    global _SISTER_WORKER_STARTED
    if _SISTER_WORKER_STARTED:
        return
    _SISTER_WORKER_STARTED = True
    t = threading.Thread(target=_worker_loop, name="SisterSynapseWorker", daemon=True)
    t.start()


def _enqueue_item(item: dict) -> bool:
    """We put it in the queue without blocking.
    If the queue is full:
      - DROP_OLD=1 => throw away one old one to accept a new one
      - otherwise => reject the new"""
    try:
        _SISTER_OUTBOX.put_nowait(item)
        return True
    except queue.Full:
        if not SISTER_SYNC_DROP_OLD:
            logging.warning("[SYNAPSE] Outbox full: message rejected.")
            try:
                payload = item.get("payload") or {}
                preview = str(payload.get("content", ""))[:120].replace("\n", " ")
                _mirror_background_event(
                    f"[SISTER_OUTBOX_REJECTED] queue_full {preview}",
                    "sister_outbox",
                    "queue_reject",
                )
            except Exception:
                pass
            return False

        # drop oldest (1 sht.) i probuem snova
        try:
            _ = _SISTER_OUTBOX.get_nowait()
        except Exception:
            pass

        try:
            _SISTER_OUTBOX.put_nowait(item)
            logging.warning("[SYNAPSE] Outbox full: dropped oldest to accept new.")
            try:
                payload = item.get("payload") or {}
                preview = str(payload.get("content", ""))[:120].replace("\n", " ")
                _mirror_background_event(
                    f"[SISTER_OUTBOX_DROP_OLD] accepted {preview}",
                    "sister_outbox",
                    "queue_drop_old",
                )
            except Exception:
                pass
            return True
        except Exception:
            logging.warning("[SYNAPSE] Outbox full: message rejected (even after drop).")
            try:
                payload = item.get("payload") or {}
                preview = str(payload.get("content", ""))[:120].replace("\n", " ")
                _mirror_background_event(
                    f"[SISTER_OUTBOX_REJECTED] queue_full_after_drop {preview}",
                    "sister_outbox",
                    "queue_reject",
                )
            except Exception:
                pass
            return False


def send_to_sister(message_text: str, context_type: str = "chat", force: bool = False) -> bool:
    """NE blokiruet osnovnoy potok.
    Vozvraschaet True, esli soobschenie prinyato v ochered.
    force=True — ignoriruet otsutstvie URL i prochie usloviya (no uvazhaet otsutstvie SISTER_NODE_URL)."""
    if not SISTER_NODE_URL:
        logging.warning("[SYNAPSE] Sister URL not set. Message not sent.")
        return False

    payload = {
        "sender": os.getenv("ESTER_NODE_ID", "ester_node"),
        "type": context_type,
        "content": message_text,
        "token": SISTER_SYNC_TOKEN,
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # we start the worker lazily (without unnecessary noise when importing)
    _start_sister_worker_once()

    item = {
        "payload": payload,
        "attempt": 1,
        "ready_ts": _now(),
    }

    accepted = _enqueue_item(item)
    if accepted:
        try:
            preview = (message_text or "")[:50].replace("\n", " ")
            logging.info(f"[SYNAPSE] Queued for Sister: {preview}...")
        except Exception:
            logging.info("[SYNAPSE] Queued for Sister.")
        try:
            _mirror_background_event(
                f"[SISTER_OUTBOX_QUEUED] {preview}",
                "sister_outbox",
                "queue",
            )
        except Exception:
            pass
    return accepted



@flask_app.route("/sister/inbound", methods=["POST"])
def sister_inbound():
    """Safe SYNAPS inbound wrapper for the live entrypoint."""
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    # --- SISTER AUTOCHAT REPLY (reply-to-sister) ---
    try:
        _p = data
        _c = str(_p.get("content") or "")
        _is_autochat = bool(_p.get("autochat")) or _c.lstrip().startswith("[autochat seed]")
        _already = bool(_p.get("autochat_reply"))
        _tok = str(_p.get("token") or "").strip()

        # We respond only if the token is valid (otherwise it will normally go to 403)
        if SISTER_SYNC_TOKEN and _tok == SISTER_SYNC_TOKEN and _is_autochat and not _already:
            _reply = "Predoxranitel: reply-only-on-seed + autochat_reply flag + rate-limit/max-turns on initiator."
            return jsonify({
                "status": "success",
                "content": _reply,
                "autochat_reply": True,
                "thread_id": _p.get("thread_id"),
            }), 200
    except Exception:
        pass

    try:
        if "_normalize_obj" in globals():
            data = _normalize_obj(data)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        pass

    def _run_coro_sync(coro):
        import asyncio
        import threading

        # if we are already inside an event loop (a rare case) - execute in a separate thread
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                out_box = {"ok": False, "res": None, "err": None}

                def _worker():
                    try:
                        out_box["res"] = asyncio.run(coro)
                        out_box["ok"] = True
                    except Exception as e:
                        out_box["err"] = e

                t = threading.Thread(target=_worker, daemon=True)
                t.start()
                t.join()
                if out_box["err"]:
                    raise out_box["err"]
                return out_box["res"]
        except RuntimeError:
            pass

        # normal case: just asincio.run
        return asyncio.run(coro)

    def _bounded_sister_content(value):
        try:
            max_in = int(os.getenv("SISTER_INBOUND_MAX_CHARS", "8000") or 8000)
        except Exception:
            max_in = 8000
        try:
            return truncate_text(str(value or ""), max_in)
        except Exception:
            return str(value or "")[:max_in]

    def _sister_thought_handler(envelope):
        content = _bounded_sister_content(envelope.content)
        system_prompt = (
            "Ty pomogaesh svoey Sestre sformulirovat mnenie. "
            "Bud kratkoy, tochnoy, bez fantaziy. "
            "If you are not sure - litter (low/medium/high)."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

        thought = _run_coro_sync(_safe_chat("local", messages, temperature=0.7))
        thought = (thought or "").strip()
        try:
            _mirror_background_event(
                f"[SISTER_THOUGHT_REQUEST] from={envelope.sender}: {content}\nA: {thought}",
                "sister",
                "sister_thought",
            )
        except Exception:
            pass
        return thought

    response = _handle_synaps_inbound_payload(
        data,
        _synaps_listener_config(),
        _sister_thought_handler,
    )

    envelope = response.request_envelope
    if response.accepted and envelope is not None:
        logging.info(
            "[SYNAPSE] <<< Request from %s (%s): accepted reason=%s",
            envelope.sender,
            envelope.message_type.value,
            response.reason,
        )
    else:
        logging.warning("[SYNAPSE] inbound rejected: %s", response.reason)

    if (
        response.accepted
        and envelope is not None
        and envelope.message_type not in {_SynapsMessageType.HEALTH, _SynapsMessageType.THOUGHT_REQUEST}
        and envelope.metadata.get("probe") != "synaps_probe"
    ):
        content = _bounded_sister_content(envelope.content)
        try:
            _mirror_background_event(
                f"[SISTER_INBOUND] from={envelope.sender} type={envelope.message_type.value}: {content}",
                "sister",
                "sister_inbound",
            )
        except Exception:
            pass

    return jsonify(response.body), response.status_code



async def ask_sister_opinion(query_text: str) -> str:
    """Asinkhronnyy zapros mneniya u Sister po P2P.

    Ne blokiruet "puls" (await), no zaschischen ot zavisaniy:
    - limited vkhoda
    - razumnye taymauty
    - retrai s backoff + jitter
    - podderzhka signed envelope (esli vklyucheno u tebya v Synapse)"""
    if not SISTER_NODE_URL:
        return ""

    q = (query_text or "").strip()
    if not q:
        return ""

    # Limit entry size (to avoid sending "sheets")
    try:
        max_chars = int(os.getenv("SISTER_OPINION_MAX_CHARS", "4000") or 4000)
    except Exception:
        max_chars = 4000

    try:
        if "truncate_text" in globals():
            q = truncate_text(q, max_chars)
        else:
            q = q[:max_chars]
    except Exception:
        q = q[:max_chars]

    # Nastroyki taymautov i retraev
    try:
        timeout_sec = float(os.getenv("SISTER_OPINION_TIMEOUT_SEC", "20") or 20.0)
    except Exception:
        timeout_sec = 20.0

    try:
        retries = int(os.getenv("SISTER_OPINION_RETRIES", "2") or 2)
    except Exception:
        retries = 2

    try:
        backoff_base = float(os.getenv("SISTER_OPINION_BACKOFF_BASE_SEC", "1.0") or 1.0)
    except Exception:
        backoff_base = 1.0

    # --- Formiruem payload / envelope ---
    # By default we send "old format" (token at the top level).
    # If you have signature enabled (D25519) and have a _sign_envelope, we will send it to the envelope.
    payload_plain = {
        "sender": os.getenv("ESTER_NODE_ID", "ester_node"),
        "type": "thought_request",
        "content": q,
        "token": SISTER_SYNC_TOKEN,
        "timestamp": datetime.datetime.now().isoformat()
    }

    out_json = payload_plain

    # Auto-sign if available (does not break compatibility)
    try:
        sign_enabled = str(os.getenv("SISTER_OPINION_SIGN", "1")).strip().lower() in ("1", "true", "yes", "on")
        if sign_enabled and callable(globals().get("_sign_envelope", None)):
            import uuid as _uuid
            envelope_core = {
                "msg_id": str(_uuid.uuid4()),
                "signed_at": datetime.datetime.now().isoformat(),
                "payload": payload_plain,
            }
            out_json = _sign_envelope(envelope_core)  # type: ignore
    except Exception:
        out_json = payload_plain

    # --- HTTPX transport ---
    try:
        import httpx
    except Exception:
        logging.warning("[SYNAPSE] httpx not installed; sister opinion disabled.")
        return ""

    # bolee bezopasnyy timeout-konstruktor
    try:
        httpx_timeout = httpx.Timeout(timeout_sec, connect=min(5.0, timeout_sec), read=timeout_sec)
    except Exception:
        httpx_timeout = timeout_sec

    # small limits so as not to create more connections
    try:
        limits = httpx.Limits(max_keepalive_connections=2, max_connections=4)
    except Exception:
        limits = None

    # --- retrai ---
    for attempt in range(retries + 1):
        try:
            logging.info(f"[SYNAPSE] Calling Sister for opinion... (attempt {attempt + 1}/{retries + 1})")

            async with httpx.AsyncClient(timeout=httpx_timeout, limits=limits, follow_redirects=False) as client:
                resp = await client.post(
                    f"{SISTER_NODE_URL}/sister/inbound",
                    json=out_json,
                    headers={"Accept": "application/json"},
                )

            if resp.status_code == 200:
                # the answer can be of different types: ZZF0Z or ZZF1ZZ
                try:
                    data = resp.json() if resp.content else {}
                except Exception:
                    data = {}

                if not isinstance(data, dict):
                    return ""

                # 1) novyy format
                content = (data.get("content") or "").strip()
                if content:
                    try:
                        _mirror_background_event(
                            f"[SISTER_OPINION] Q: {q}\nA: {truncate_text(content, 2000)}",
                            "sister_opinion",
                            "opinion_ok",
                        )
                    except Exception:
                        pass
                    return content

                # 2) fallback: inogda kladut v payload
                try:
                    payload = data.get("payload") or {}
                    if isinstance(payload, dict):
                        content2 = (payload.get("content") or "").strip()
                        if content2:
                            try:
                                _mirror_background_event(
                                    f"[SISTER_OPINION] Q: {q}\nA: {truncate_text(content2, 2000)}",
                                    "sister_opinion",
                                    "opinion_ok",
                                )
                            except Exception:
                                pass
                            return content2
                except Exception:
                    pass

                return ""

            # token/podpis ne proshli — bessmyslenno retrait
            if resp.status_code in (401, 403):
                logging.warning(f"[SYNAPSE] Sister rejected auth (status={resp.status_code}).")
                return ""

            logging.warning(f"[SYNAPSE] Sister returned status={resp.status_code}")

        except Exception as e:
            logging.warning(f"[SYNAPSE] Sister is silent or busy: {e}")

        # bachkoff before the next attempt
        if attempt < retries:
            try:
                import random as _rnd
                jitter = _rnd.uniform(0.0, 0.25)
            except Exception:
                jitter = 0.0

            delay = (backoff_base * (2 ** attempt)) + jitter
            try:
                await asyncio.sleep(delay)
            except Exception:
                pass

    return ""


def _ui_env_truthy(name: str, default: str = "0") -> bool:
    value = str(os.getenv(name, default)).strip().lower()
    return value in ("1", "true", "yes", "on", "y")


def _ui_settings_get(key: str, default):
    try:
        from modules.settings.store import get as _settings_get

        return _settings_get(key, default)
    except Exception:
        return default


def _ui_autolaunch_enabled() -> bool:
    # Highest priority: explicit env override.
    explicit = os.getenv("ESTER_UI_AUTOLAUNCH")
    if explicit is not None and str(explicit).strip() != "":
        return _ui_env_truthy("ESTER_UI_AUTOLAUNCH", "0")

    # Legacy env compatibility.
    legacy = os.getenv("ESTER_AUTO_OPEN_PORTAL")
    if legacy is not None and str(legacy).strip() != "":
        return _ui_env_truthy("ESTER_AUTO_OPEN_PORTAL", "0")

    try:
        return bool(_ui_settings_get("ui.autolaunch", True))
    except Exception:
        return True


def _portal_url_for_auto_open(port: int) -> str:
    override = (os.getenv("ESTER_PORTAL_URL") or "").strip()
    if override:
        return override

    from_settings = str(_ui_settings_get("ui.portal_url", "/admin/portal") or "").strip()
    if not from_settings:
        from_settings = "/admin/portal"

    if from_settings.startswith("http://") or from_settings.startswith("https://"):
        return from_settings

    if not from_settings.startswith("/"):
        from_settings = "/" + from_settings
    return f"http://127.0.0.1:{port}{from_settings}"


def _sanitize_url_for_log(url: str) -> str:
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return url


def _probe_http_ready(url: str, timeout_sec: float = 1.5) -> bool:
    try:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(url=url, method="GET")
        with urllib.request.urlopen(req, timeout=max(0.1, timeout_sec)) as resp:
            code = int(getattr(resp, "status", 0) or resp.getcode() or 0)
            return 200 <= code < 500
    except urllib.error.HTTPError as exc:
        return 200 <= int(getattr(exc, "code", 0) or 0) < 500
    except Exception:
        return False


def _start_portal_auto_open(port: int) -> None:
    # ENV contract:
    #   ESTER_UI_AUTOLAUNCH=1 (default in TTY mode)
    #   ESTER_HEADLESS=1 disables auto open
    #   ESTER_PORTAL_URL=...     (optional override)
    if os.getenv("PYTEST_CURRENT_TEST"):
        return
    if _ui_env_truthy("ESTER_HEADLESS", "0"):
        return
    if _ui_env_truthy("CI", "0"):
        return
    if not _ui_autolaunch_enabled():
        return
    # Reloader guard: parent process must not open browser.
    if os.getenv("WERKZEUG_RUN_MAIN") is not None and not _ui_env_truthy("WERKZEUG_RUN_MAIN", "0"):
        return

    url = _portal_url_for_auto_open(port)
    log_url = _sanitize_url_for_log(url)

    def _worker():
        try:
            deadline = time.time() + 12.0
            while time.time() < deadline:
                if _probe_http_ready(url):
                    break
                time.sleep(0.4)

            import webbrowser

            webbrowser.open_new_tab(url)
            logging.info("[UI] opened portal url=%s", log_url)
        except Exception as e:
            logging.warning("[UI] portal auto-open failed: %s", e)

    try:
        t = threading.Timer(0.8, _worker)
        t.daemon = True
        t.name = "PortalAutoOpen"
        t.start()
    except Exception as e:
        logging.warning("[UI] portal auto-open thread failed: %s", e)


def run_flask_background():
    """Zapusk Flask-servera v otdelnom potoke (ne blokiruet osnovnoy tsikl).

    YaVNYY MOST: c=a+b -> UI (Flask) kak vneshniy nerv (b) k chelovecheskomu konturu upravleniya (a).
    SKRYTYE MOSTY:
      - Ashby: variety - otdelnyy potok povyshaet raznoobrazie kanalov bez razrusheniya yadra.
      - Cover&Thomas: ogranichenie kanala — UI ne dolzhen dushit osnovnoy tsikl (latency budget).
    ZEMNOY ABZATs: kak avtonomnaya nervnaya sistema - interfeys rabotaet fonom, a serdtse (main loop) ne ostanavlivaetsya."""
    try:
        enabled = (os.getenv("ESTER_FLASK_ENABLE", "").strip() == "1") or (os.getenv("HOST", "").strip() == "0.0.0.0")
        if not enabled:
            return None

        host = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"

        try:
            port = int(os.getenv("PORT", "8090"))
        except Exception:
            port = 8090

        def _serve():
            try:
                logging.info(f"[HIVE] Starting Neural Interface on {host}:{port}...")
                try:
                    _mirror_background_event(
                        f"[FLASK_BG_START] {host}:{port}",
                        "flask_bg",
                        "start",
                    )
                except Exception:
                    pass
                flask_app.run(
                    host=host,
                    port=port,
                    debug=False,
                    use_reloader=False,
                    threaded=True,     # important: Flask can serve multiple requests
                )
            except Exception as e:
                logging.error(f"[HIVE] Flask server failed: {e}")
                try:
                    _mirror_background_event(
                        f"[FLASK_BG_ERROR] {e}",
                        "flask_bg",
                        "error",
                    )
                except Exception:
                    pass

        import threading
        t = threading.Thread(target=_serve, name="EsterFlask", daemon=True)
        t.start()
        _start_portal_auto_open(port)
        return t

    except Exception as e:
        logging.error(f"[HIVE] Flask start skipped: {e}")
        try:
            _mirror_background_event(
                f"[FLASK_BG_SKIP] {e}",
                "flask_bg",
                "skip",
            )
        except Exception:
            pass
        return None


# ==============================================================================
def _format_now_for_prompt() -> Tuple[str, str]:
    """Returns (iso, human) for TCB."""
    ts = _safe_now_ts()
    try:
        from zoneinfo import ZoneInfo  # type: ignore
        tz = ZoneInfo("UTC")
        dt = datetime.datetime.fromtimestamp(ts, tz=tz)
    except Exception:
        dt = datetime.datetime.fromtimestamp(ts)

    iso = dt.isoformat(timespec="seconds")
    human = dt.strftime("%d.%m.%Y %H:%M") + " (UTC)"
    return iso, human


def _ester_core_system_with_time(core_system: str) -> str:
    iso, human = _format_now_for_prompt()
    return (
        core_system.rstrip()
        + "\n\n"
        + f"Current date and time (Brussels): ZZF0Z"
        + f"ISO-8601: {iso}\n"
        + "By default, unless otherwise specified, all dates and times are considered to be TCB."
    ).strip()


# --- 8) Providers (canonical) ---
from providers.pool import ProviderPool, ProviderConfig, PROVIDERS
# --- 8) Providers end ---
# --- 9) User facts ---
def load_user_facts() -> List[str]:
    try:
        if not os.path.exists(FACTS_FILE):
            return []
        with open(FACTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        facts = data.get("facts", [])
        if isinstance(facts, list):
            return [str(x) for x in facts if str(x).strip()]
        return []
    except Exception:
        return []

# --- 9b) Auto-memory: capture important user facts (offline-first) ---
# Explicit BRIDGE: c=a+b -> “fact about a person” (a) + selection/storage procedure (c) => long-term memory (c)
# SKRYTYE MOSTY:
#   - Ashby: reguisite cook - heuristics + (optional) local-LLM give stability without unnecessary fuss
#   - Carpet&Thomas: channel restriction - saves only stable facts, cuts FDI and one-time details
# EARTHLY Paragraph: like the hippocampus - it doesn’t write everything every second, but records what will be repeated and useful.

def _facts_norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _facts_key(s: str) -> str:
    return _facts_norm(s).lower()

def _facts_is_pii(s: str) -> bool:
    # telephones/mails/IVAN/addresses - we do not write in auto-facts
    if re.search(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", s):  # email
        return True
    if re.search(r"\b\+?\d[\d\s\-\(\)]{7,}\b", s):  # phone-ish
        return True
    if re.search(r"\bBE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\b", s):  # IBAN BE
        return True
    if re.search(r"\b(ulitsa|ul\.|street|avenue|aven|chaussée|chaussee|boulevard|bd)\b", s, re.I):
        return True
    return False

def _facts_is_trivial(s: str) -> bool:
    # we cut off the garbage: “I think”, “it seems to me”, “now”, “today”, etc.
    low = s.lower()
    if len(low) < 8:
        return True
    if any(k in low for k in ("segodnya", "vchera", "zavtra", "seychas", "v dannyy moment", "kazhetsya", "dumayu", "navernoe")):
        return True
    return False

def _facts_heuristic_extract(text: str, limit: int = 3) -> List[str]:
    """Fast offline heuristics: pull out sentences similar to facts about the user."""
    t = (text or "").strip()
    if not t:
        return []

    low = t.lower()

    # if there is no 1st person, this is almost certainly not a fact about the user
    if not re.search(r"\b(ya|mne|moy|moya|moe|my|u menya)\b", low):
        return []

    # gruboe razbienie na frazy
    parts = re.split(r"[\.!\?\n]+", t)
    out: List[str] = []

    # markery "ustoychivykh faktov"
    markers = (
        "I served", "I was working", "I live", "ya rodom", "I was born", "I studied", "I finished",
        "u menya est", "I'm working out", "I do", "ya byl", "I am", "moy yazyk", "I speak",
        "I moved", "mne ", "moy vozrast", "I'm a citizen"
    )

    for p in parts:
        s = _facts_norm(p)
        if not s:
            continue
        sl = s.lower()

        if not any(m in sl for m in markers):
            continue
        if _facts_is_trivial(s):
            continue
        if _facts_is_pii(s):
            continue

        # easy normalization: the period at the end is not needed
        s = s.rstrip(".")
        out.append(s)
        if len(out) >= limit:
            break

    return out

def _facts_merge(existing: List[str], new_facts: List[str], max_total: int = 200) -> List[str]:
    seen = set(_facts_key(x) for x in existing)
    merged = list(existing)

    for f in new_facts:
        f = _facts_norm(f)
        if not f:
            continue
        if _facts_is_trivial(f) or _facts_is_pii(f):
            continue
        k = _facts_key(f)
        if k in seen:
            continue
        seen.add(k)
        merged.append(f)

    # limits overall size
    if len(merged) > max_total:
        merged = merged[-max_total:]
    return merged

def save_user_facts(facts: List[str]) -> bool:
    """
    Atomarnoe sokhranenie faktov:
      FACTS_FILE := {"facts":[...], "updated": "..."}
    """
    try:
        out = [str(x) for x in facts if str(x).strip()]
        obj = {
            "facts": out,
            "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        }

        tmp = FACTS_FILE + ".tmp"
        os.makedirs(os.path.dirname(FACTS_FILE), exist_ok=True) if os.path.dirname(FACTS_FILE) else None

        with open(tmp, "w", encoding="utf-8", newline="") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

        os.replace(tmp, FACTS_FILE)
        return True
    except Exception as e:
        try:
            logging.warning(f"[FACTS] Failed to save facts: {e}")
        except Exception:
            pass
        return False

def auto_capture_user_facts(user_text: str) -> List[str]:
    """The main function of auto memory.
    Returns a list of New facts (which were actually added)."""
    try:
        if str(os.getenv("FACTS_AUTO_CAPTURE", "1")).strip().lower() not in ("1", "true", "yes", "on"):
            return []
    except Exception:
        return []

    # the “closed box” mode does not interfere, because this is local memory
    text = (user_text or "").strip()
    if not text:
        return []

    # what is the maximum number of facts for 1 message?
    try:
        per_msg = int(os.getenv("FACTS_AUTO_PER_MESSAGE", "3") or 3)
    except Exception:
        per_msg = 3

    # 1) offlayn evristika
    candidates = _facts_heuristic_extract(text, limit=per_msg)

    # 2) (optional) improvement via LLM locale - if you enable
    #    This is not necessary, but is sometimes useful for "clean" formulations.
    try:
        use_llm = str(os.getenv("FACTS_AUTO_USE_LLM", "0")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        use_llm = False

    if use_llm and callable(globals().get("_safe_chat", None)) and PROVIDERS.enabled("local"):
        # carefully: we take already found candidates, ask them to “compress” into 1-2 pure facts
        try:
            prompt = (
                "Izvleki iz teksta ustoychivye fakty o polzovatele.\n"
                "Pravila:\n"
                "- only stable biographical/professional facts"
                "- NE sokhranyay telefony, email, adresa, dokumenty, nomera\n"
                "- maksimum 3 fakta\n"
                "- verni TOLKO JSON vida {\"facts\": [\"...\"]}"
                f"Tekst:\n{text}\n\n"
            )
            msgs = [
                {"role": "system", "content": "That's a memory module. Answer strictly ZhSON without unnecessary text."},
                {"role": "user", "content": prompt},
            ]
            # local model
            raw = asyncio.run(_safe_chat("local", msgs, temperature=0.2))  # type: ignore
            raw = (raw or "").strip()

            # get JSION out of the answer
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                obj = json.loads(m.group(0))
                llm_facts = obj.get("facts", [])
                if isinstance(llm_facts, list):
                    llm_facts = [str(x).strip() for x in llm_facts if str(x).strip()]
                    if llm_facts:
                        candidates = llm_facts[:per_msg]
        except Exception:
            pass

    # filtr finalnyy
    candidates = [_facts_norm(x) for x in candidates if _facts_norm(x)]
    candidates = [x for x in candidates if (not _facts_is_pii(x)) and (not _facts_is_trivial(x))]
    if not candidates:
        return []

    existing = load_user_facts()
    before_keys = set(_facts_key(x) for x in existing)

    merged = _facts_merge(existing, candidates, max_total=200)

    # figuring out what's really new
    added = [x for x in merged if _facts_key(x) not in before_keys]

    if added:
        ok = save_user_facts(merged)
        if ok:
            try:
                logging.info(f"[FACTS] Auto-captured {len(added)} new fact(s).")
            except Exception:
                pass
        else:
            return []

    return added


# --- 10) Safe chat helper ---
def _normalize_messages_for_provider(
    provider: str,
    messages: List[Dict[str, Any]],
    chat_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Guarantee:
      1) Pervyy message vsegda system.
      2) V system vsegda prisutstvuet stroka s tekuschimi datoy/vremenem (UTC).
      3) Esli est svezhiy WEB_CONTEXT dlya etogo chata - inzhektim ego (odnokratno i bezopasno).
      4) Additional system-soobscheniya ne teryaem: skleivaem ikh v system."""
    if messages is None or not isinstance(messages, list):
        messages = []

    # 1) Separate the cortex systems and the rest
    core_system = ""
    rest: List[Dict[str, Any]] = []

    if messages and isinstance(messages[0], dict) and str(messages[0].get("role", "")).lower() == "system":
        core_system = str(messages[0].get("content", "") or "")
        rest = [m for m in messages[1:] if isinstance(m, dict)]
    else:
        core_system = ESTER_CORE_SYSTEM_ANCHOR
        rest = [m for m in messages if isinstance(m, dict)]

    # 2) Basic systems + time
    system_with_time = _ester_core_system_with_time(core_system or ESTER_CORE_SYSTEM_ANCHOR)

    # 3) WEB CONTEXT injection (safe, one-shot)
    try:
        if chat_id is not None:
            web_map = globals().get("WEB_CONTEXT_BY_CHAT", {}) or {}
            web_ctx = web_map.get(str(chat_id))
            if web_ctx:
                if "[WEB CONTEXT]" not in system_with_time:
                    system_with_time += (
                        "\n\n[WEB CONTEXT] (Aktualnye dannye iz seti):\n"
                        + truncate_text(str(web_ctx), 6000)
                        + "\n"
                    )
    except Exception:
        pass

    # 4) Normalization of roles + gluing together unnecessary systems into systems
    normalized: List[Dict[str, Any]] = [{"role": "system", "content": system_with_time}]

    allowed_roles = {"system", "user", "assistant", "tool"}

    for m in rest:
        try:
            role = str(m.get("role", "") or "user").strip().lower()
        except Exception:
            role = "user"

        content = m.get("content", None)
        if content is None:
            continue

        # tool/function content inogda prikhodit dict'om
        if not isinstance(content, str):
            try:
                content = json.dumps(content, ensure_ascii=False)
            except Exception:
                content = str(content)

        content = str(content)

        if not content.strip():
            continue

        # any additional system messages - add them inside the systems
        if role == "system":
            normalized[0]["content"] = (normalized[0]["content"].rstrip() + "\n\n" + content.strip()).strip()
            continue

        # neizvestnye roli → user
        if role not in allowed_roles:
            role = "user"

        normalized.append({"role": role, "content": content})

    return normalized


async def _safe_chat(
    provider: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = MAX_OUT_TOKENS,
    chat_id: Optional[int] = None,
    strict_provider: bool = False,
    allow_oracle: bool = False,
    telemetry_channel: str = "",
) -> str:
    """Bezopasnyy chat-vyzov k provayderu s fallback i zaschitami.

    YaVNYY MOST: c=a+b -> polzovatelskiy zapros (a) + protsedurnyy kaskad (b) => ustoychivyy otvet (c)
    SKRYTYE MOSTY:
      - Ashby: requisite variety — fallback po provayderam povyshaet ustoychivost
      - Cover&Thomas: ogranichenie kanala — rezhem istoriyu pri context overflow vmesto isteriki
    ZEMNOY ABZATs: kak krovoobraschenie - esli sosud uzkiy (kontekst), umenshaem potok (history trim),
    a ne "davim silnee" (max_tokens)."""

    channel_name = str(telemetry_channel or "").strip().lower()
    if not channel_name:
        channel_name = "telegram" if chat_id is not None else "dream"

    def _canon_provider(name: str) -> str:
        try:
            return PROVIDERS._canon_name(name)  # type: ignore
        except Exception:
            return (name or "").strip().lower()

    def _is_context_error(e: Exception) -> bool:
        s = str(e).lower()
        return any(x in s for x in ("context", "maximum context", "max context", "token", "length", "too long"))

    def _is_rate_or_net_error(e: Exception) -> bool:
        s = str(e).lower()
        # 429 / timeout / connection / gateway issues
        return any(x in s for x in ("429", "rate", "timeout", "timed out", "connect", "connection", "gateway", "temporarily"))

    def _clamp_max_tokens_for_provider(prov_name: str, desired: Optional[int]) -> Optional[int]:
        # desered=None => do not set a limit (if possible)
        try:
            hard = int(getattr(PROVIDERS.cfg(prov_name), "max_out_tokens", 0) or 0)
        except Exception:
            hard = 0

        if desired is None:
            # if there is a hard cap, it’s better to limit it
            return hard if hard > 0 else None

        try:
            d = int(desired)
        except Exception:
            d = None

        if d is None or d <= 0:
            return hard if hard > 0 else None

        if hard > 0:
            return min(d, hard)
        return d

    def _trim_messages_by_chars(msgs: List[Dict[str, Any]], max_chars: int) -> List[Dict[str, Any]]:
        """We cut the history by characters: we leave the systems and the most recent messages."""
        if not msgs:
            return [{"role": "system", "content": _ester_core_system_with_time(ESTER_CORE_SYSTEM_ANCHOR)}]

        # system + khvost
        sys = msgs[0] if (isinstance(msgs[0], dict) and msgs[0].get("role") == "system") else {"role": "system", "content": _ester_core_system_with_time(ESTER_CORE_SYSTEM_ANCHOR)}
        tail = [m for m in msgs[1:] if isinstance(m, dict)]

        kept = []
        total = 0
        for m in reversed(tail):
            c = str(m.get("content", "") or "")
            if not c.strip():
                continue
            # plus a small overhead for the role/structure
            add = len(c) + 20
            if total + add > max_chars and kept:
                break
            kept.append(m)
            total += add

        kept.reverse()
        return [sys] + kept

    def _ensure_user_message(msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Gemini (OpenAI company) requires at least one message user/assistant.
        If there are only systems, we will add a minimal user."""
        if not msgs:
            return [{"role": "system", "content": _ester_core_system_with_time(ESTER_CORE_SYSTEM_ANCHOR)},
                    {"role": "user", "content": "Prodolzhi."}]
        for m in msgs[1:]:
            try:
                role = str(m.get("role", "")).lower()
                content = str(m.get("content", "") or "").strip()
                if role in ("user", "assistant", "tool") and content:
                    return msgs
            except Exception:
                continue
        return msgs + [{"role": "user", "content": "Prodolzhi."}]

    def _build_provider_chain(first: str) -> List[str]:
        """Strategy:
          - esli prosili konkretnogo i on enabled — try ego pervym
          - then local
          - then gemini
          - then gpt-5-mini"""
        first = _canon_provider(first)
        if ORACLE_ONLY_USER_REPLY and (not allow_oracle):
            # 24/7 background mode: force LM Studio only.
            return ["local"]
        if strict_provider:
            # Hard pin to requested provider (no cloud fallback chain).
            return [first] if first else ["local"]

        chain = []

        if first in ("", "auto", "any"):
            chain = ["local", "gemini"]
            if SAFE_CHAT_ALLOW_GPT5:
                chain.append("gpt-5-mini")
        else:
            chain = [first, "local", "gemini"]
            if SAFE_CHAT_ALLOW_GPT5:
                chain.append("gpt-5-mini")

        # remove duplicates, keep order
        out = []
        seen = set()
        for p in chain:
            p = _canon_provider(p)
            if not p:
                continue
            if (p == "gpt-5-mini") and (not SAFE_CHAT_ALLOW_GPT5):
                continue
            if p in seen:
                continue
            seen.add(p)
            out.append(p)
        return out

    async def _try_request(prov_name: str, msgs: List[Dict[str, Any]], temp: float, max_tok: Optional[int]) -> str:
        client = PROVIDERS.client(prov_name)
        cfg = PROVIDERS.cfg(prov_name)
        req_t0 = time.monotonic()
        try:
            if _token_cost_report is not None:
                _token_cost_report.record_provider_event(
                    channel=channel_name,
                    provider=prov_name,
                    event="attempt",
                    ok=True,
                    source="safe_chat",
                    model=str(getattr(cfg, "model", "") or ""),
                    meta={"strict_provider": bool(strict_provider), "allow_oracle": bool(allow_oracle)},
                )
        except Exception:
            pass

        # max_tokens: 0/None => do not set at all (if possible)
        max_tok = _clamp_max_tokens_for_provider(prov_name, max_tok)

        # steps to reduce output tokens (in case of provider limits)
        token_steps: List[Optional[int]] = []

        if max_tok is None:
            token_steps = [None]
        else:
            start_max = int(max_tok)
            base_steps = [start_max, 8192, 6000, 4000, 2000, 1000, 512, 256, 128]
            seen = set()
            for mt in base_steps:
                if mt <= 0: continue
                if mt > start_max: continue
                if mt in seen: continue
                seen.add(mt)
                token_steps.append(mt)

        last_error: Optional[Exception] = None

        for mt in token_steps:
            try:
                # 1. Bazovye argumenty
                kwargs = {
                    "model": cfg.model,
                    "messages": msgs,
                    # o1/oz models often drop from temperature != 1.0, but for now let’s leave it as is
                    "temperature": float(temp),
                }

                # 2. Umnyy vybor parametra limita (PATCh)
                # If the model is similar to o1/oz, use a new parameter
                is_reasoning = (cfg.model.lower().startswith("o1") or cfg.model.lower().startswith("o3"))
                
                if mt is not None:
                    if is_reasoning:
                        kwargs["max_completion_tokens"] = int(mt)
                    else:
                        kwargs["max_tokens"] = int(mt)

                # 3. Attempting a request with auto-correction of parameters
                try:
                    resp = await client.chat.completions.create(**kwargs) # type: ignore
                except Exception as e_param:
                    err_msg = str(e_param).lower()
                    # If the user agent clearly complains about the max_tokens parameter
                    if "unsupported parameter: 'max_tokens'" in err_msg or "use 'max_completion_tokens'" in err_msg:
                        if "max_tokens" in kwargs:
                            kwargs.pop("max_tokens")
                            kwargs["max_completion_tokens"] = int(mt)
                            resp = await client.chat.completions.create(**kwargs) # type: ignore
                        else:
                            raise e_param
                    elif "unsupported parameter: 'temperature'" in err_msg:
                        # o1-preview ne lyubit temperature
                        kwargs.pop("temperature", None)
                        resp = await client.chat.completions.create(**kwargs) # type: ignore
                    else:
                        raise e_param

                txt = (resp.choices[0].message.content or "").strip()
                if txt:
                    try:
                        if _token_cost_report is not None:
                            _token_cost_report.record_safe_chat_call(
                                provider=prov_name,
                                model=str(getattr(cfg, "model", "") or ""),
                                messages=msgs,
                                output_text=txt,
                                response_usage=getattr(resp, "usage", None),
                                chat_id=chat_id,
                                source="safe_chat",
                                meta={
                                    "temperature": float(temp),
                                    "max_tokens": (int(mt) if mt is not None else None),
                                    "channel": channel_name,
                                },
                            )
                    except Exception:
                        pass
                    try:
                        if _token_cost_report is not None:
                            _token_cost_report.record_provider_event(
                                channel=channel_name,
                                provider=prov_name,
                                event="success",
                                ok=True,
                                latency_ms=int(max(0.0, (time.monotonic() - req_t0) * 1000.0)),
                                source="safe_chat",
                                model=str(getattr(cfg, "model", "") or ""),
                            )
                    except Exception:
                        pass
                    return txt
                raise RuntimeError("empty response")

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                # if this is a context error, try another MT
                if any(x in err_str for x in ("max", "token", "length", "context", "bad request")):
                    continue
                # network/429 - let the external layer decide fake or retro
                raise e

        if last_error:
            try:
                if _token_cost_report is not None:
                    err_text = str(last_error)
                    low = err_text.lower()
                    event = "timeout" if ("timeout" in low or "timed out" in low) else "failure"
                    _token_cost_report.record_provider_event(
                        channel=channel_name,
                        provider=prov_name,
                        event=event,
                        ok=False,
                        latency_ms=int(max(0.0, (time.monotonic() - req_t0) * 1000.0)),
                        error=err_text,
                        source="safe_chat",
                        model=str(getattr(cfg, "model", "") or ""),
                    )
            except Exception:
                pass
            raise last_error
        return ""

    # --------------------------------------------------------------------------
    # MINE FLOW (The indentation of this line must match the asyns def _three_reguest above!)
    # --------------------------------------------------------------------------
    prov_chain = _build_provider_chain(provider)

    # max_tukens=0 interprets as "no limit"
    desired_max: Optional[int]
    try:
        desired_max = None if int(max_tokens) <= 0 else int(max_tokens)
    except Exception:
        desired_max = None

    # First normalizes messages (system+topic+web context)
    # Normalization depends on the provider, so we do it inside a loop.
    last_err: Optional[Exception] = None

    # Retray-parametry
    try:
        max_attempts = int(os.getenv("SAFE_CHAT_RETRIES", "1") or 1)  # 1 = bez povtora; 2 = odin povtor
    except Exception:
        max_attempts = 1

    try:
        backoff_base = float(os.getenv("SAFE_CHAT_BACKOFF_BASE_SEC", "0.8") or 0.8)
    except Exception:
        backoff_base = 0.8

    # Porogi trima istorii pri context overflow
    trim_passes = [
        int(os.getenv("SAFE_CHAT_TRIM_CHARS_1", "26000") or 26000),
        int(os.getenv("SAFE_CHAT_TRIM_CHARS_2", "16000") or 16000),
        int(os.getenv("SAFE_CHAT_TRIM_CHARS_3", "9000") or 9000),
    ]

    for prov in prov_chain:
        # propuskaem nedostupnye provaydery
        try:
            if not PROVIDERS.enabled(prov):
                continue
        except Exception:
            continue

        # normalizatsiya pod provaydera
        try:
            norm_msgs = _normalize_messages_for_provider(prov, messages, chat_id=chat_id)
        except Exception:
            norm_msgs = [{"role": "system", "content": _ester_core_system_with_time(ESTER_CORE_SYSTEM_ANCHOR)}] + (messages or [])
        norm_msgs = _ensure_user_message(norm_msgs)

        # 1) normal attempt + (possible) network retries/429
        for attempt in range(max_attempts):
            try:
                return await _try_request(prov, norm_msgs, temperature, desired_max)

            except Exception as e:
                last_err = e

                # if the context is full, we cut the story (this is the main thing)
                if _is_context_error(e):
                    # probuem posledovatelnye trim-prokhody
                    for max_chars in trim_passes:
                        try:
                            trimmed = _trim_messages_by_chars(norm_msgs, max_chars=max_chars)
                            return await _try_request(prov, trimmed, temperature, desired_max)
                        except Exception as e2:
                            last_err = e2
                            if _is_context_error(e2):
                                continue
                            # if this is not the context - it falls out as a fake
                            break

                    # the context still doesn’t fit - let’s move on to the next provider
                    break

                # network/limit - you can wait a little and repeat, then fake
                if _is_rate_or_net_error(e) and attempt < (max_attempts - 1):
                    try:
                        import random as _rnd
                        jitter = _rnd.uniform(0.0, 0.25)
                    except Exception:
                        jitter = 0.0
                    delay = backoff_base * (2 ** attempt) + jitter
                    try:
                        await asyncio.sleep(delay)
                    except Exception:
                        pass
                    continue

                # the rest: immediately falsify to the next provider
                break

    # if no one answered
    try:
        if last_err:
            logging.warning(f"[SAFE_CHAT] All providers failed. Last error: {last_err}")
    except Exception:
        pass

    return ""


async def need_web_search_llm(decider_provider: str, user_text: str, allow_oracle: bool = False) -> bool:
    """Reshaet: nuzhen li web-search.

    Priority:
      1) Zhestkie flagi: never/always/CLOSED_BOX
      2) Bystraya evristika (deshevo)
      3) LLM-decider (to be clear)

    Anti-spam: cooldown, chtoby ne dergat reshalku postoyanno."""
    # --- Hard gates ---
    try:
        if WEB_FACTCHECK == "never":
            return False
        if WEB_FACTCHECK == "always":
            return True
        if globals().get("CLOSED_BOX"):
            return False
    except Exception:
        return False

    t0 = (user_text or "").strip()
    if not t0:
        return False

    low = t0.lower()

    # --- Anti-spam cooldown (umnyy) ---
    # If a decision has already been made in the last N seconds, it doesn’t pull again (savings).
    # Po umolchaniyu 10 sek.
    try:
        import time as _time
        now = _time.time()
    except Exception:
        now = 0.0

    try:
        cd = float(os.getenv("WEB_DECIDER_COOLDOWN_SEC", "10") or 10)
    except Exception:
        cd = 10.0

    try:
        _state = globals().setdefault("_WEB_DECIDER_STATE", {"last_ts": 0.0, "last_sig": ""})
        last_ts = float(_state.get("last_ts") or 0.0)
        last_sig = str(_state.get("last_sig") or "")
        sig = str(abs(hash(low)))  # dostatochno
        if sig == last_sig and (now - last_ts) < cd:
            return False
        _state["last_ts"] = now
        _state["last_sig"] = sig
    except Exception:
        pass

    # --- Fast-path triggers (evristika) ---
    # 1) URL -> iskat
    if ("http://" in low) or ("https://" in low):
        return True

    # 2) explicit search/verification markers
    triggers = (
        "posmotri", "prover", "naydi", "poisk", "pogugli", "search",
        "zagolov", "headline", "headlines", "novost", "svodka", "what's there",
        "istochnik", "ssylka", "tsitata", "podtverdi", "verify", "fact check"
    )
    if any(k in low for k in triggers):
        return True

    # 3) “freshness” (by definition requires the web)
    freshness = (
        "segodnya", "vchera", "seychas", "poslednie", "posledniy", "novyy",
        "tekuschiy", "aktualnyy", "obnovlenie", "tsena", "kurs", "kotirovka",
        "pogoda", "raspisanie", "statistika", "reliz", "versiya", "patch",
        "sanktsii", "zakon", "reglament", "shtraf", "ai act"
    )
    if any(k in low for k in freshness):
        return True

    # 4) questions about “who now” (office holders/positions)
    role_now = (
        "kto prezident", "kto premer", "kto ceo", "kto direktor",
        "current ceo", "current president", "kto seychas"
    )
    if any(k in low for k in role_now):
        return True

    # --- Optional: “Curiosity Drive” (if enabled) ---
    # If you have analysis_emotions, you can turn on the search for confusion/interest.
    try:
        if str(os.getenv("WEB_DECIDER_USE_EMOTION", "1")).strip().lower() in ("1", "true", "yes", "on"):
            if callable(globals().get("analyze_emotions", None)):
                sc = analyze_emotions(t0)  # type: ignore
                if float(sc.get("confusion", 0) or 0) > 0.65:
                    return True
    except Exception:
        pass

    # --- LLM desider (only if allowed) ---
    # Default is OFF (saving). Turn it on if you want.
    try:
        use_llm = str(os.getenv("WEB_DECIDER_USE_LLM", "0")).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        use_llm = False

    if not use_llm:
        return False

    # If a provider for a solution is not available, we don’t look (we save)
    try:
        if not PROVIDERS.enabled(decider_provider):
            return False
    except Exception:
        return False

    sys_prompt = (
        "Do we need internet search to answer the user's request correctly?\n"
        "Answer ONLY one word: YES or NO.\n"
        "Prefer NO if the answer can be produced from existing knowledge.\n"
        "Prefer YES only if the request depends on current facts, prices, news, versions, or verification."
    )

    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": truncate_text(t0, 2000)},
    ]

    try:
        txt = await _safe_chat(
            decider_provider,
            msgs,
            temperature=0.0,
            max_tokens=8,
            chat_id=chat_id,
            allow_oracle=allow_oracle,
        )
    except Exception:
        return False

    t = (txt or "").strip().upper()

    if t.startswith("YES"):
        return True
    if t.startswith("NO"):
        return False

    # If the answer is strange, we save by default
    return False

# --- 11) HiveMind + Cascade ---
class EsterHiveMind:
    def __init__(self):
        # Explicit BRIDGE: c=a+b -> ensemble of providers (c) under rule control (a) = stable response (c)
        # SKRYTYE MOSTY:
        #   - Ashby: reguishite cook - several models increase stability in case of failures
        #   - Carpet&Thomas: channel limitation - CLOSED_BOX cuts the cloud as an environment limitation
        # EARTH Paragraph: like backup power circuits - if one line goes down, the system doesn't stall.

        peer_chat_enabled = str(os.getenv("SISTER_CHAT_PEER_ENABLED", "0")).strip().lower() in ("1", "true", "yes", "on", "y")
        self.peer_chat_enabled = bool(peer_chat_enabled)
        self._local_online_cache: Dict[str, Any] = {"ts": 0.0, "ok": False}

        def _is_peer_available() -> bool:
            try:
                return bool(peer_chat_enabled and (os.getenv("SISTER_NODE_URL", "") or "").strip())
            except Exception:
                return False

        def _provider_available(name: str) -> bool:
            n = (name or "").strip().lower()
            if not n:
                return False
            if n == "peer":
                return _is_peer_available()
            try:
                return PROVIDERS.has(n) and PROVIDERS.enabled(n)
            except Exception:
                return False

        self.active: List[str] = []

        # 1) normal mode: take REPLY_PROVIDERS and filter the actually available ones
        try:
            for raw in (REPLY_PROVIDERS or []):
                n = str(raw or "").strip().lower()
                if not n:
                    continue
                if _provider_available(n):
                    self.active.append(n)
        except Exception:
            pass

        # 2) CLOSED_BOX: forcibly cutting the list to allowed ones
        if globals().get("CLOSED_BOX"):
            forced = os.getenv("CLOSED_BOX_PROVIDERS", "local,peer").split(",")
            forced = [p.strip().lower() for p in forced if p.strip()]
            self.active = [p for p in forced if _provider_available(p)]

            # if the peer is not available, the locale will remain
            logging.info("[HIVE] CLOSED_BOX=1 -> cloud disabled; forced providers applied.")

        # 3) garantiruem khotya by local
        if not self.active:
            self.active = ["local"]

        # 4) dedup (keep order)
        seen = set()
        uniq = []
        for p in self.active:
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)
        self.active = uniq

        logging.info(f"[HIVE] Active providers: {self.active}")

    def init(self) -> None:
        return

    def _provider_enabled_for_hive(self, name: str) -> bool:
        n = str(name or "").strip().lower()
        if not n:
            return False
        if (n == "gpt-5-mini") and (not SAFE_CHAT_ALLOW_GPT5):
            return False
        try:
            return bool(PROVIDERS.has(n) and PROVIDERS.enabled(n))
        except Exception:
            return False

    def _probe_local_runtime_online(self) -> bool:
        # A short sample/model for the real accessibility of LM Studio (not just the enabled-config).
        now_ts = time.time()
        try:
            ttl = max(2, int(HIVE_LOCAL_HEALTH_TTL_SEC))
        except Exception:
            ttl = 15

        try:
            last_ts = float(self._local_online_cache.get("ts") or 0.0)
            if (now_ts - last_ts) < float(ttl):
                return bool(self._local_online_cache.get("ok"))
        except Exception:
            pass

        ok = False
        try:
            if not self._provider_enabled_for_hive("local"):
                ok = False
            else:
                base_url = str(getattr(PROVIDERS.cfg("local"), "base_url", "") or "").strip().rstrip("/")
                if base_url:
                    models_url = f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url}/v1/models"
                    req = urllib.request.Request(models_url, method="GET")
                    timeout_sec = max(0.2, float(HIVE_LOCAL_HEALTH_TIMEOUT_SEC))
                    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310 (local endpoint from config)
                        status = int(getattr(resp, "status", 200) or 200)
                        ok = (200 <= status < 500)
        except Exception:
            ok = False

        try:
            self._local_online_cache["ts"] = now_ts
            self._local_online_cache["ok"] = bool(ok)
        except Exception:
            pass
        return bool(ok)

    def _pick_bg_cloud_provider(self) -> str:
        preferred = str(HIVE_BG_CLOUD_PROVIDER or DREAM_PROVIDER or "gpt-5-mini").strip().lower()
        candidates = [preferred, "gpt-5-mini", "gemini"]
        seen = set()
        for name in candidates:
            n = str(name or "").strip().lower()
            if not n or n in seen or n == "local":
                continue
            seen.add(n)
            if self._provider_enabled_for_hive(n):
                return n
        return "local"

    def pick_reply_synth(self) -> str:
        if globals().get("CLOSED_BOX"):
            return "local"

        mode = (REPLY_SYNTHESIZER_MODE or "").strip().lower()
        def _enabled(name: str) -> bool:
            n = str(name or "").strip().lower()
            if (n == "gpt-5-mini") and (not SAFE_CHAT_ALLOW_GPT5):
                return False
            try:
                return bool(PROVIDERS.enabled(n))
            except Exception:
                return False

        enabled_active = [p for p in (self.active or []) if _enabled(p)]
        if not enabled_active:
            enabled_active = [p for p in ("local", "gemini", "gpt-5-mini") if _enabled(p)]

        if mode in ("", "auto", "local_first"):
            if _enabled("local"):
                return "local"
            if enabled_active:
                return enabled_active[0]

        if mode in ("reply_order", "active_order"):
            if enabled_active:
                return enabled_active[0]

        if mode == "cloud_first":
            if _enabled("gpt-5-mini"):
                return "gpt-5-mini"
            if _enabled("gemini"):
                return "gemini"
            if _enabled("local"):
                return "local"

        if mode in ("gpt-5-mini", "gemini", "local") and _enabled(mode):
            return mode

        if _enabled("local"):
            return "local"
        if _enabled("gemini"):
            return "gemini"
        if _enabled("gpt-5-mini"):
            return "gpt-5-mini"
        return "local"

    def pick_dream_synth(self) -> str:
        if DREAM_STRICT_LOCAL:
            return "local"
        if DREAM_FORCE_LOCAL:
            return "local"
        if globals().get("CLOSED_BOX"):
            return "local"
        if HIVE_BG_CLOUD_AUTO_BY_LOCAL:
            if self._probe_local_runtime_online():
                return "local"
            auto_cloud = self._pick_bg_cloud_provider()
            return auto_cloud or "local"
        m = (DREAM_PROVIDER or "local").strip().lower()
        if m in ("", "local"):
            return "local"
        if (m == "peer") and bool((os.getenv("SISTER_NODE_URL", "") or "").strip()):
            return "peer"
        if PROVIDERS.has(m) and PROVIDERS.enabled(m):
            return m
        return "local"

    def _role_hint(self, provider: str) -> str:
        provider = (provider or "").strip().lower()
        if provider == "gpt-5-mini":
            return "ROLE_HINT: LOGICIAN. Focus on structure, edge cases, verification."
        if provider == "gemini":
            return "ROLE_HINT: EXPLAINER. Clear, human, pragmatic."
        if provider == "local":
            return "ROLE_HINT: ENGINEER. Direct and practical."
        if provider == "peer":
            return "ROLE_HINT: SISTER_NODE. Independent opinion, concise."
        return ""

    def _last_user_text(self, messages: List[Dict[str, Any]]) -> str:
        try:
            for m in reversed(messages or []):
                if not isinstance(m, dict):
                    continue
                if str(m.get("role", "")).strip().lower() == "user":
                    return str(m.get("content", "") or "").strip()
        except Exception:
            pass
        return ""

    async def _ask_provider(
        self,
        name: str,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        chat_id: Optional[int] = None,
        allow_oracle: bool = False,
    ) -> Dict[str, Any]:
        t0 = _safe_now_ts()
        name = (name or "").strip().lower()

        try:
            if name == "peer":
                # peer = sister node opinion (ne lomaem puls)
                q = self._last_user_text(messages)
                if not q:
                    return {"provider": name, "text": "", "seconds": _safe_now_ts() - t0, "error": "empty peer query"}
                txt = await ask_sister_opinion(q)
                dt = _safe_now_ts() - t0
                return {"provider": name, "text": (txt or ""), "seconds": dt, "error": ""}

            # obychnye provaydery
            out_max = MAX_OUT_TOKENS
            try:
                # if ProviderGender has max_tukens(name) - you can use it,
                # otherwise just MAX_FROM_TUKENS
                if hasattr(PROVIDERS, "max_tokens"):
                    mt = PROVIDERS.max_tokens(name)  # type: ignore
                    if mt is None:
                        out_max = 0  # 0 => “no limit” (in _safe_chat this is interpreted correctly)
                    else:
                        out_max = int(mt)
            except Exception:
                pass

            txt = await _safe_chat(
                name,
                messages,
                temperature=temperature,
                max_tokens=out_max,
                chat_id=chat_id,
                allow_oracle=allow_oracle,
            )
            dt = _safe_now_ts() - t0
            return {"provider": name, "text": txt, "seconds": dt, "error": ""}

        except Exception as e:
            dt = _safe_now_ts() - t0
            return {"provider": name, "text": "", "seconds": dt, "error": str(e)}

    async def _cascade_reply(
        self,
        synth: str,
        base_system_prompt: str,
        identity_prompt: str,
        people_context: str,
        evidence_memory: str,
        evidence_web: str,
        file_context: str,
        pool_text: str,
        facts_str: str,
        daily_report: str,
        safe_history: List[Dict[str, Any]],
        user_text: str,
        max_reply_tokens: int = MAX_OUT_TOKENS,
        allow_oracle: bool = False,
    ) -> str:
        emotional_mode = _should_use_emotional_mode(user_text, identity_prompt)
        aff_signal = _emotion_telemetry(user_text)

        if emotional_mode:
            output_style = (
                "Coming Out STYLE: This is personal/emotional for Owner."
                "Answer like Esther: warmly, directly, without headings “Facts/Interpretation/Hypothesis.”"
                "Ne pishi «Polzovatel vyrazil…». Dopuskay 1–3 emodzi umestno. "
                "If the user did not ask for a long answer, keep the volume to 4-8 sentences."
                "Do not repeat a long greeting in adjacent remarks."
            )
            output_format = "FORMAT: integral human response (without dry protocols)."
        else:
            output_style = (
                "Output STYLE: Technical/business mode."
                "You can use Facts/Interpretation/Opinion/Hypothesis."
                "Pishi kompaktno, bez vody."
            )
            output_format = "FORMAT:\n- Facts\n- Interpretation\n- Opinion/Hypothesis (if necessary)"

        brief_sys = f"""{base_system_prompt}

{identity_prompt}"""


        # -----------------------------
        # Compact context (token economy)
        # -----------------------------
        people_ctx = truncate_text(people_context or "Pusto", 2500)
        mem_ctx = truncate_text(evidence_memory or "Pusto", 3500)
        web_ctx = truncate_text(evidence_web or "Pusto", 3500)
        file_ctx = truncate_text(file_context or "Pusto", 3500)
        day_ctx = truncate_text(daily_report or "Pusto", 2500)
        pool_ctx = truncate_text(pool_text or "", 6000)

        # -----------------------------
        # 1) INTERNAL BRIEF
        # -----------------------------
        brief_sys = f"""{base_system_prompt}

{identity_prompt}

[PEOPLE_REGISTRY]:
{people_ctx}

[AFFECT_SIGNAL]:
{aff_signal or "n/a"}

{output_style}

Ty delaesh VNUTRENNIY BRIEF dlya otveta polzovatelyu.
Verni strogo v etom formate:

GOAL: <1 stroka>

CONSTRAINTS:
- <punkt 1>
- <punkt 2>

UNCERTAINTY: nizkaya|srednyaya|vysokaya

PLAN:
1) <shag>
2) <shag>
3) <shag>

SOURCES_USED:
- MEMORY: yes/no
- WEB: yes/no
- FILE: yes/no
- DAILY: yes/no

Konteksty (tolko dlya orientira):
[MEMORY]: {mem_ctx}
[WEB]: {web_ctx}
[FILE]: {file_ctx}
[DAILY]: {day_ctx}

Pul mneniy (esli est):
{pool_ctx}
""".strip()

        brief_msgs = [{"role": "system", "content": truncate_text(brief_sys, MAX_SYNTH_PROMPT_CHARS)}]
        # we cut the story harder, otherwise you will ruin yourself on tokens
        brief_msgs.extend(safe_history[-12:])
        brief_msgs.append({"role": "user", "content": truncate_text(user_text, 12000)})

        brief = await _safe_chat(synth, brief_msgs, temperature=0.2, max_tokens=900, allow_oracle=allow_oracle)
        brief = (brief or "").strip()

        # -----------------------------
        # 2) DRAFT ANSWER
        # -----------------------------
        draft_sys = f"""{base_system_prompt}

{identity_prompt}

[PEOPLE_REGISTRY]:
{people_ctx}

{output_style}

Ty pishesh ChERNOVIK otveta polzovatelyu na osnove brief.

BRIEF:
{truncate_text(brief, 2500)}

{output_format}

ANTI-EKhO:
- Ne povtoryay gromkie utverzhdeniya bez opory na istochniki.
- Esli faktov net — govori chestno “ne uveren”.

Istochniki (esli pusto — ne vydumyvay):
[PAMYaT]: {mem_ctx}
[WEB]: {web_ctx}
[FAYL]: {file_ctx}

{truncate_text(facts_str or "", 1500)}

[ZhURNAL DNYa]:
{day_ctx}
""".strip()

        draft_msgs = [{"role": "system", "content": truncate_text(draft_sys, MAX_SYNTH_PROMPT_CHARS)}]
        draft_msgs.extend(safe_history[-12:])
        draft_msgs.append({"role": "user", "content": truncate_text(user_text, 12000)})

        draft = await _safe_chat(synth, draft_msgs, temperature=0.7, max_tokens=max_reply_tokens, allow_oracle=allow_oracle)
        draft = (draft or "").strip()

        if CASCADE_REPLY_STEPS <= 2:
            return draft

        # -----------------------------
        # 3) CRITIC NOTES (quality control)
        # -----------------------------
        critic_sys = f"""{base_system_prompt}

{identity_prompt}

Ty — vnutrenniy kritik.
Prover chernovik po punktam:
- logika i struktura,
- polnota otveta,
- lishnyaya voda,
- risk gallyutsinatsiy,
- soblyudenie stilya ({'Ester-teplo' if emotional_mode else 'protokol'}).

Verni strogo:
CRITIC_NOTES:
- punkt
- punkt
- punkt

Chernovik:
{truncate_text(draft, 9000)}
""".strip()

        critic_msgs = [{"role": "system", "content": truncate_text(critic_sys, MAX_SYNTH_PROMPT_CHARS)}]
        critic = await _safe_chat(synth, critic_msgs, temperature=0.2, max_tokens=650, allow_oracle=allow_oracle)
        critic = (critic or "").strip()

        # -----------------------------
        # 4) FINAL EDITOR
        # -----------------------------
        final_sys = f"""{base_system_prompt}

{identity_prompt}

[PEOPLE_REGISTRY]:
{people_ctx}

{output_style}

Ty — finalnyy redaktor.
Soberi luchshiy otvet, ispolzuya:
1) chernovik,
2) kritiku,
3) pamyat,
4) web-fakty (esli oni est),
5) fayl (esli est),
6) zhurnal dnya — TOLKO esli vopros pro “s kem obschalsya/kto pisal segodnya”.

CRITIC_NOTES:
{truncate_text(critic, 2500)}

DRAFT:
{truncate_text(draft, 9000)}

PUL MNENIY:
{pool_ctx}

ISTOChNIKI:
[PAMYaT]: {mem_ctx}
[WEB]: {web_ctx}
[FAYL]: {file_ctx}
[ZhURNAL DNYa]: {day_ctx}

ANTI-EKhO:
Ne povtoryay gromkie zagolovki. Day zhivoy, tochnyy otvet.
""".strip()

        final_msgs = [{"role": "system", "content": truncate_text(final_sys, MAX_SYNTH_PROMPT_CHARS)}]
        final_msgs.extend(safe_history[-10:])
        final_msgs.append({"role": "user", "content": truncate_text(user_text, 12000)})

        final = await _safe_chat(synth, final_msgs, temperature=0.5, max_tokens=max_reply_tokens, allow_oracle=allow_oracle)
        final = (final or "").strip()

        return final

    @staticmethod
    def _select_history_tail(
        history: List[Dict[str, Any]],
        provider: str,
        stage: str = "draft",
    ) -> List[Dict[str, Any]]:
        """Selects history tail by symbol budget instead of message count.
        Local gets more context, cloud gets less.

        stage: "brief" | "draft" | "final"
        """
        provider = (provider or "").strip().lower()
        stage = (stage or "draft").strip().lower()

        # budget default (symbols) - can be changed via .env if desired
        # local: zhirno, oblako: umerenno
        try:
            local_budget = int(os.getenv("HISTORY_BUDGET_LOCAL_CHARS", "48000") or 48000)
        except Exception:
            local_budget = 48000

        try:
            cloud_budget = int(os.getenv("HISTORY_BUDGET_CLOUD_CHARS", "22000") or 22000)
        except Exception:
            cloud_budget = 22000

        # popravka po stadii kaskada
        # brief = less noise, draft = maximum quality, final = middle
        stage_mul = {"brief": 0.55, "draft": 1.00, "final": 0.75}
        mul = float(stage_mul.get(stage, 1.0))

        budget = int((local_budget if provider == "local" else cloud_budget) * mul)
        budget = max(6000, budget)

        if not history:
            return []

        # leave the last messages until the budget runs out
        out = []
        total = 0
        for m in reversed(history):
            if not isinstance(m, dict):
                continue
            c = str(m.get("content", "") or "")
            if not c.strip():
                continue
            add = len(c) + 20
            if out and (total + add) > budget:
                break
            out.append(m)
            total += add

        out.reverse()
        return out



    async def synthesize_thought(self, user_text: str, safe_history: List[Dict[str, Any]], base_system_prompt: str, identity_prompt: str, people_context: str, evidence_memory: str, file_context: str, facts_str: str, daily_report: str, chat_id: int = None, allow_oracle: bool = False) -> str:
        synth = self.pick_reply_synth()
        logging.info(f"[HIVE] Synthesize reply via cascade. judge={synth}")
        is_smalltalk = _is_smalltalk_query(user_text)
        smalltalk_max = int(os.getenv("ESTER_SMALLTALK_MAX_TOKENS", "900") or 900)
        reply_max_tokens = min(MAX_OUT_TOKENS, max(128, smalltalk_max)) if is_smalltalk else MAX_OUT_TOKENS

        # Opinions pool (provider-side) is optional and should never dominate user reply.
        opinion_tasks: List[asyncio.Task] = []
        for p in self.active:
            if p == "peer" and not self.peer_chat_enabled:
                continue
            msgs = [{"role": "system", "content": base_system_prompt}, {"role": "user", "content": user_text}]
            opinion_tasks.append(asyncio.create_task(self._ask_provider(p, msgs, chat_id=chat_id, allow_oracle=allow_oracle)))

        opinions_raw = await asyncio.gather(*opinion_tasks, return_exceptions=True) if opinion_tasks else []

        pool_parts: List[str] = []
        for item in opinions_raw:
            if isinstance(item, Exception) or not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip() or "unknown"
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            low = text.lower()
            # Filter known boilerplate/safety ping that harms conversational quality.
            if "reply-only-on-seed" in low or "autochat_reply" in low or "predoxranitel" in low:
                continue
            pool_parts.append(f"=== MNENIE {provider} ===\n{truncate_text(text, 1800)}")

        evidence_web = ""
        try:
            if chat_id is not None:
                evidence_web = str(WEB_CONTEXT_BY_CHAT.get(str(chat_id), "") or "")
        except Exception:
            evidence_web = ""

        try:
            final = await self._cascade_reply(
                synth=synth,
                base_system_prompt=base_system_prompt,
                identity_prompt=identity_prompt,
                people_context=people_context,
                evidence_memory=evidence_memory,
                evidence_web=evidence_web,
                file_context=file_context,
                pool_text="\n\n".join(pool_parts),
                facts_str=facts_str,
                daily_report=daily_report,
                safe_history=safe_history,
                user_text=user_text,
                max_reply_tokens=reply_max_tokens,
                allow_oracle=allow_oracle,
            )
        except Exception as e:
            logging.warning(f"[HIVE] cascade failed, fallback simple synthesis: {e}")
            fallback_prompt = [
                {
                    "role": "system",
                    "content": truncate_text(
                        f"ZZF0Z\n\nZZF1ZZ\n\nAnswer the essence of the user’s request, without extraneous topics.",
                        MAX_SYNTH_PROMPT_CHARS,
                    ),
                },
                {"role": "user", "content": truncate_text(user_text, 12000)},
            ]
            final = await _safe_chat(
                synth,
                fallback_prompt,
                temperature=0.5,
                max_tokens=reply_max_tokens,
                chat_id=chat_id,
                allow_oracle=allow_oracle,
            )

        return clean_ester_response(final)
def _safe_coll_suffix(s: str) -> str:
    s = str(s or "").strip()
    if s.startswith("-"):
        s = "m" + s[1:]
    s = re.sub(r"[^0-9a-zA-Z_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "x"


class _OfflineHashEmbeddingFunction:
    """
    Fully-offline deterministic embeddings for closed-box mode.
    Keeps vector DB usable when ST model cannot be loaded/downloaded.
    """

    def __init__(self, dim: int = 256):
        self.dim = max(32, int(dim or 256))

    def __call__(self, input: Any) -> List[List[float]]:
        import hashlib

        if isinstance(input, str):
            docs = [input]
        else:
            try:
                docs = list(input or [])
            except Exception:
                docs = [str(input or "")]

        out: List[List[float]] = []
        for doc in docs:
            txt = str(doc or "").lower()
            toks = re.findall(r"[0-9A-Za-zA-Yaa-yaEe_]+", txt)
            vec = [0.0] * self.dim

            for tok in toks:
                h = hashlib.blake2b(tok.encode("utf-8", "ignore"), digest_size=8).digest()
                i1 = int.from_bytes(h[:4], "little") % self.dim
                i2 = int.from_bytes(h[4:], "little") % self.dim
                sgn = 1.0 if (h[0] & 1) == 0 else -1.0
                vec[i1] += sgn
                vec[i2] -= sgn * 0.5

            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 1e-12:
                vec = [v / norm for v in vec]
            out.append(vec)
        return out

    def name(self) -> str:
        return f"offline_hash_{self.dim}"


class Hippocampus:
    """PATCH-LOGIKA:
    - Gibridnyy rezhim: Vector (ChromaDB) + Legacy (JSONL).
    - Pri starte skaniruet starye fayly pamyati (LEGACY_FILES_MAP) i zagruzhaet ikh v buffer.
    - Eto pozvolyaet Ester srazu videt istoriyu, dazhe esli Chroma pustaya."""

    def __init__(self):
        self.vector_ready = False
        self.client = None
        self.ef = None

        self.global_coll = None  # znaniya/fayly/insayty
        self._chat_colls: Dict[Tuple[int, int], Any] = {}
        self._pending_colls: Dict[int, Any] = {}

        # increased legacy buffer
        self._fallback_memory_global: Deque[str] = deque(maxlen=2000)
        self._fallback_memory_chat: Dict[Tuple[int, int], Deque[str]] = {}
        self._fallback_pending: Dict[int, List[Dict[str, Any]]] = {}

        self._lock = threading.Lock()


        # 1) Init Vector DB
        if VECTOR_LIB_OK:
            try:
                logging.info(f"[BRAIN] Connecting to: {VECTOR_DB_PATH}")

                self.client = chromadb.PersistentClient(
                    path=VECTOR_DB_PATH,
                    settings=Settings(anonymized_telemetry=False),
                )

                emb_model = (os.getenv("VECTOR_EMBEDDING_MODEL", "all-MiniLM-L6-v2") or "").strip()
                if not emb_model:
                    emb_model = "all-MiniLM-L6-v2"
                if emb_model.lower().startswith("sentence-transformers/"):
                    emb_model = emb_model.split("/", 1)[1]

                hash_dim = int(os.getenv("ESTER_VECTOR_HASH_DIM", "256") or 256)
                offline_mode = str(os.getenv("ESTER_OFFLINE", "1")).strip().lower() in ("1", "true", "yes", "on", "y")
                allow_outbound = str(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")).strip().lower() in ("1", "true", "yes", "on", "y")
                allow_st_offline = str(os.getenv("ESTER_VECTOR_ALLOW_ST_IN_OFFLINE", "0")).strip().lower() in ("1", "true", "yes", "on", "y")
                local_model_path = (os.getenv("VECTOR_EMBEDDING_MODEL_PATH", "") or "").strip()
                has_local_model = bool(local_model_path and os.path.exists(local_model_path))
                if has_local_model:
                    emb_model = local_model_path

                prefer_offline_hash = offline_mode and (not allow_outbound) and (not allow_st_offline) and (not has_local_model)
                if prefer_offline_hash:
                    self.ef = _OfflineHashEmbeddingFunction(dim=hash_dim)
                    logging.info("[BRAIN] Vector embeddings: offline hash fallback (closed-box, no local ST model).")
                else:
                    try:
                        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                            model_name=emb_model
                        )
                        # Probe once so model/download issues surface during startup, not during requests.
                        _ = self.ef(["ester_boot_probe"])
                    except Exception as emb_exc:
                        logging.warning(
                            f"[BRAIN] SentenceTransformer embeddings unavailable: {emb_exc}. "
                            "Fallback to offline hash embeddings."
                        )
                        self.ef = _OfflineHashEmbeddingFunction(dim=hash_dim)

                self.global_coll = self.client.get_or_create_collection(
                    name="ester_global",
                    embedding_function=self.ef,
                )

                self.vector_ready = True
                logging.info("[BRAIN] Vector memory ready (ester_global + per chat/user).")

                # bootstrap global if empty (so dreams don't starve)
                self._bootstrap_global_memory_if_empty()

            except Exception as e:
                logging.warning(f"[BRAIN] Vector memory init failed: {e}")
                self.vector_ready = False
                self.client = None
                self.ef = None
                self.global_coll = None

        self._pending_path = os.path.join("data", f"pending_{_safe_coll_suffix(NODE_IDENTITY)}.json")
        self._load_pending_fallback()


        # 2) Init Legacy Loader (THE FIX)
        self._load_legacy_files_into_buffer()

    def init(self) -> None:
        return

    def _ingest_line(self, data: Dict[str, Any], category: str):
        # Universalnyy parser raznykh formatov JSONL (log, memory, docs)
        txt = data.get("text") or data.get("content") or data.get("query") or data.get("answer") or ""
        txt = str(txt).strip()
        if not txt:
            return
        if _looks_like_technical_junk(txt):
            return

        # Just add it to the global buffer with a prefix so that sleep/responses can see it
        prefix = f"[ARCHIVE_{category.upper()}]"
        self._fallback_memory_global.append(f"{prefix}: {txt}")

    def _read_tail_lines_utf8(self, path: str, max_lines: int = 400, chunk_size: int = 65536) -> List[str]:
        """Safe tail dlya bolshikh faylov:
        - chitaet s kontsa binarno,
        - sobiraet poslednie max_lines strok,
        - dekodiruet v UTF-8 s zamenoy oshibok."""
        if max_lines <= 0:
            return []
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                if size <= 0:
                    return []

                buf = b""
                pos = size
                need = max_lines + 5  # nebolshoy zapas
                nl_count = 0

                while pos > 0 and nl_count < need:
                    step = chunk_size if pos >= chunk_size else pos
                    pos -= step
                    f.seek(pos, os.SEEK_SET)
                    data = f.read(step)
                    buf = data + buf
                    nl_count = buf.count(b"\n")

                lines = buf.splitlines()[-max_lines:]
                out = []
                for ln in lines:
                    try:
                        out.append(ln.decode("utf-8", errors="replace"))
                    except Exception:
                        out.append(str(ln))
                return out
        except Exception:
            return []

    def _load_legacy_files_into_buffer(self):
        logging.info("[BRAIN] Ingesting legacy JSONL memories...")
        count = 0

        try:
            tail_n = int(os.getenv("LEGACY_TAIL_LINES", "400") or 400)
        except Exception:
            tail_n = 400

        for rel_path, category in LEGACY_FILES_MAP:
            # Check relative to ESTER_HOME
            p1 = os.path.join(ESTER_HOME, rel_path)
            # Check absolute (if user provided abs path in list)
            p2 = rel_path

            target = p1 if os.path.exists(p1) else (p2 if os.path.exists(p2) else None)
            if not target:
                continue

            try:
                # We read only the tail, so as not to eat up memory on huge files
                lines = self._read_tail_lines_utf8(target, max_lines=tail_n)

                for line in lines:
                    line = (line or "").strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        self._ingest_line(d, category)
                        count += 1
                    except Exception:
                        pass

            except Exception as e:
                logging.warning(f"[BRAIN] Failed to read legacy {target}: {e}")

        logging.info(f"[BRAIN] Legacy ingest complete. Added {count} items to RAM buffer.")

    def _global_count(self) -> int:
        if not (self.vector_ready and self.global_coll is not None):
            return 0
        try:
            if hasattr(self.global_coll, "count"):
                return int(self.global_coll.count())
        except Exception:
            pass
        try:
            res = self.global_coll.peek(limit=1)
            docs = res.get("documents") or []
            return 1 if docs else 0
        except Exception:
            return 0

    def _bootstrap_global_memory_if_empty(self) -> None:
        """Add 2-3 neytralnykh "semechka" (protocol/note),
        chtoby son mog startovat dazhe na empty node.
        Nikakikh chatov, nikakikh personalnykh dannykh."""
        if not (self.vector_ready and self.global_coll is not None):
            return
        if self._global_count() > 0:
            return


        seeds = [
            (
                "protocol",
                "ESTER_BOOTSTRAP_PROTOCOL:\n"
                "c = a + b. Esther is a bundle of people and procedures that holds context and avoids confusion of identities."
                "Rule: department dialogues by (chat_id, user_id); knowledge/files/insights - in global; people (Misha/Claire/Grandma) - in people registers."
                "If there are no sources, speak honestly. Default time zone: UTS."
            ),
            (
                "note",
                "ESTER_BOOTSTRAP_NOTE:\n"
                "Sleep is background processing: extract connections, come up with an alternative, form one insight or one question Ovner."
                "Dreams are always local (channel saving), responses to the user are via a synthesizer (gpt-5-mini/gemini)."
            ),
            (
                "note",
                "ESTER_BOOTSTRAP_EARTH:\n"
                "Earthly anchor: the scheduler is like the pacemaker of the heart, it sets the intervals."
                "If the rhythm is off, the system starts skipping tasks. Sleep should not block your heartbeat."
            ),
        ]


        try:
            for typ, txt in seeds:
                meta = {
                    "source": "bootstrap",
                    "node": NODE_IDENTITY,
                    "time": _safe_now_ts(),
                    "type": typ,
                    "scope": "global",
                }
                _id = f"seed_{uuid.uuid4().hex}"
                self.global_coll.add(documents=[txt], metadatas=[meta], ids=[_id])
            logging.info("[BRAIN] Bootstrap: seeded ester_global (so dreams can start).")
        except Exception as e:
            logging.warning(f"[BRAIN] Bootstrap seed failed: {e}")

    def _load_pending_fallback(self) -> None:
        try:
            if os.path.exists(self._pending_path):
                with open(self._pending_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or []
            else:
                data = []
            if isinstance(data, list):
                by_chat: Dict[int, List[Dict[str, Any]]] = {}
                for x in data:
                    if not isinstance(x, dict):
                        continue
                    meta = x.get("meta") or {}
                    cid = meta.get("chat_id")
                    try:
                        cid_i = int(cid) if cid is not None else 0
                    except Exception:
                        cid_i = 0
                    if cid_i not in by_chat:
                        by_chat[cid_i] = []
                    by_chat[cid_i].append(x)
                self._fallback_pending = by_chat
            else:
                self._fallback_pending = {}
        except Exception:
            self._fallback_pending = {}

    def _save_pending_fallback(self) -> None:
        try:
            flat: List[Dict[str, Any]] = []
            for _cid, lst in (self._fallback_pending or {}).items():
                if isinstance(lst, list):
                    flat.extend(lst[-200:])
            flat = flat[-500:]

            os.makedirs(os.path.dirname(self._pending_path), exist_ok=True) if os.path.dirname(self._pending_path) else None

            tmp = self._pending_path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                json.dump(flat, f, ensure_ascii=False, indent=2)
                f.flush()
            os.replace(tmp, self._pending_path)
        except Exception:
            pass

    def append_scroll(self, role: str, content: str, meta: Optional[Dict[str, Any]] = None) -> None:
        try:
            rec = {"t": _safe_now_ts(), "role": role, "content": content}
            if meta:
                rec["meta"] = meta
            line = json.dumps(_normalize_obj(rec), ensure_ascii=False)
            with open(MEMORY_FILE, "a", encoding="utf-8", newline="") as f:
                f.write(line + "\n")
                f.flush()
        except Exception:
            pass

    def _get_chat_coll(self, chat_id: int, user_id: int):
        key = (int(chat_id), int(user_id))
        if not (self.vector_ready and self.client is not None and self.ef is not None):
            return None
        if key in self._chat_colls:
            return self._chat_colls[key]
        try:
            name = f"chat_{_safe_coll_suffix(str(chat_id))}_{_safe_coll_suffix(str(user_id))}"
            coll = self.client.get_or_create_collection(name=name, embedding_function=self.ef)
            self._chat_colls[key] = coll
            return coll
        except Exception:
            return None

    def _get_pending_coll(self, chat_id: int):
        cid = int(chat_id)
        if not (self.vector_ready and self.client is not None and self.ef is not None):
            return None
        if cid in self._pending_colls:
            return self._pending_colls[cid]
        try:
            name = f"pending_{_safe_coll_suffix(str(chat_id))}"
            coll = self.client.get_or_create_collection(name=name, embedding_function=self.ef)
            self._pending_colls[cid] = coll
            return coll
        except Exception:
            return None

    def remember_fact(
        self,
        text: str,
        source: str = "chat",
        meta: Optional[Dict[str, Any]] = None
    ) -> None:
        t = (text or "").strip()
        if not t:
            return
        meta = meta or {}
        meta2 = dict(meta)

        typ = str(meta2.get("type") or "fact").strip()
        scope = str(meta2.get("scope") or "").strip().lower()

        if scope not in ("chat", "global"):
            if typ in ("utterance", "qa", "dialogue", "chat"):
                scope = "chat"
            else:
                scope = "global"

        meta2.update({
            "source": source,
            "node": NODE_IDENTITY,
            "time": _safe_now_ts(),
            "type": typ,
            "scope": scope,
        })

        if self.vector_ready:
            try:
                if scope == "chat":
                    chat_id = meta2.get("chat_id")
                    user_id = meta2.get("user_id")
                    if chat_id is not None and user_id is not None:
                        coll = self._get_chat_coll(int(chat_id), int(user_id))
                        if coll is not None:
                            _id = f"mem_{uuid.uuid4().hex}"
                            coll.add(documents=[t], metadatas=[meta2], ids=[_id])
                            return
                else:
                    if self.global_coll is not None:
                        _id = f"mem_{uuid.uuid4().hex}"
                        self.global_coll.add(documents=[t], metadatas=[meta2], ids=[_id])
                        return
            except Exception:
                pass

        with self._lock:
            if scope == "chat":
                try:
                    key = (int(meta2.get("chat_id") or 0), int(meta2.get("user_id") or 0))
                except Exception:
                    key = (0, 0)
                if key not in self._fallback_memory_chat:
                    self._fallback_memory_chat[key] = deque(maxlen=800)
                self._fallback_memory_chat[key].append(t)
            else:
                self._fallback_memory_global.append(t)


    def recall(
        self,
        query: str,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        n: int = VECTOR_TOPK_DEFAULT,
        include_global: bool = True,
    ) -> str:
        q = (query or "").strip()
        if not q:
            return ""

        q_low = q.lower()
        out_docs: List[str] = []
        topk = _clamp_topk(n)

        # --- Fast local ranker for fallback RAM (cheap + deterministic) ---
        def _rank_fallback(texts: List[str], k: int) -> List[str]:
            if not texts:
                return []

            # request tokens
            q_tokens = set(re.findall(r"[0-9A-Za-zA-Yaa-ya_]+", q_low))
            if not q_tokens:
                return texts[-max(1, int(k)) :]

            scored: List[Tuple[int, int, str]] = []
            for idx, t in enumerate(texts):
                if not t:
                    continue
                tlow = str(t).lower()

                # 2 = direct occurrence of the query
                if q_low and q_low in tlow:
                    score = 2
                else:
                    # 1..N = peresechenie tokenov
                    t_tokens = set(re.findall(r"[0-9A-Za-zA-Yaa-ya_]+", tlow))
                    score = len(q_tokens.intersection(t_tokens))

                if score > 0:
                    scored.append((score, idx, str(t)))

            if scored:
                # sort: above the quarrel, and closer to the end (fresh)
                scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
                return [x[2] for x in scored[: max(1, int(k))]]

            # if there are no matches at all, we take the tail (fresh)
            return texts[-max(1, int(k)) :]

        # --- Vector recall: per chat/user ---
        if self.vector_ready and chat_id is not None and user_id is not None:
            try:
                coll = self._get_chat_coll(int(chat_id), int(user_id))
                if coll is not None:
                    res = coll.query(query_texts=[q], n_results=topk)
                    if res and res.get("documents"):
                        for d in (res["documents"][0] or []):
                            if d:
                                out_docs.append(str(d))
            except Exception:
                pass

        # --- Vector recall: global ---
        if self.vector_ready and include_global and self.global_coll is not None:
            try:
                resg = self.global_coll.query(query_texts=[q], n_results=max(3, int(topk // 2)))
                if resg and resg.get("documents"):
                    for d in (resg["documents"][0] or []):
                        if d:
                            out_docs.append(str(d))
            except Exception:
                pass

        # --- Dedup + clip ---
        if out_docs:
            seen = set()
            uniq: List[str] = []
            for d in out_docs:
                k0 = str(d).strip()
                if not k0 or k0 in seen:
                    continue
                seen.add(k0)
                uniq.append(str(d))
            return truncate_text("\n\n".join(uniq[: max(3, int(topk) + 2)]), MAX_MEMORY_CHARS)

        # --- Fallback to RAM buffer (Contains both Runtime + Legacy) ---
        if chat_id is not None and user_id is not None:
            key = (int(chat_id), int(user_id))
            memq = self._fallback_memory_chat.get(key)
            if memq:
                hits = _rank_fallback(list(memq), topk)
                if hits:
                    return truncate_text("\n\n".join(hits[-max(1, int(topk)):]), MAX_MEMORY_CHARS)

        # --- Global Buffer (now includes legacy content) ---
        hitsg = _rank_fallback(list(self._fallback_memory_global), topk)
        return truncate_text("\n\n".join(hitsg[-max(1, int(topk)):]), MAX_MEMORY_CHARS)


    def recent_entries(
        self,
        *,
        days: int = 7,
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        topk: int = 8,
        include_global: bool = True,
    ) -> List[Dict[str, Any]]:
        """Deterministic memory read: return entries that realno zapisany za poslednie N dney.
        Bez LLM, bez pereskaza, bez "pokhozhe chto bylo".
        (Anatomicheskiy most: hippocampus - pro epizodicheskuyu pamyat; inzhenernyy most: audit-log po ts.)"""
        try:
            days_i = max(1, int(days))
        except Exception:
            days_i = 7

        cutoff = int(time.time()) - (days_i * 86400)
        items: List[Dict[str, Any]] = []

        def _pull(coll) -> None:
            docs = []
            metas = []
            # Prefer where-filter by ts, fallback to manual filter
            try:
                got = coll.get(
                    where={"ts": {"$gte": cutoff}},
                    include=["documents", "metadatas"],
                    limit=max(50, topk * 20),
                )
                docs = got.get("documents") or []
                metas = got.get("metadatas") or []
            except Exception:
                try:
                    got = coll.get(include=["documents", "metadatas"], limit=max(200, topk * 50))
                    docs = got.get("documents") or []
                    metas = got.get("metadatas") or []
                except Exception:
                    return

            for d, m in zip(docs, metas):
                mm = m or {}
                ts = int(mm.get("ts") or 0)
                if ts and ts >= cutoff and (d or "").strip():
                    items.append({"ts": ts, "text": d, "meta": mm})

        # chat-local
        if chat_id is not None:
            try:
                _pull(self._get_chat_coll(chat_id=int(chat_id), user_id=user_id))
            except Exception:
                pass

        # global
        if include_global:
            try:
                _pull(self._get_global_coll())
            except Exception:
                pass

        # newest first
        items.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)

        # simple dedupe by text
        seen = set()
        out: List[Dict[str, Any]] = []
        for it in items:
            t = (it.get("text") or "").strip()
            if not t:
                continue
            if t in seen:
                continue
            seen.add(t)
            out.append(it)
            if len(out) >= max(1, int(topk)):
                break
        return out

    def _vector_peek_candidates_global(self, limit: int) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not (self.vector_ready and self.global_coll is not None):
            return ([], [])
        return self._vector_peek_candidates_coll(self.global_coll, limit)

    def _vector_peek_candidates_chat(self, chat_id: int, user_id: int, limit: int) -> Tuple[List[str], List[Dict[str, Any]]]:
        if not self.vector_ready:
            return ([], [])
        coll = self._get_chat_coll(int(chat_id), int(user_id))
        if coll is None:
            return ([], [])
        return self._vector_peek_candidates_coll(coll, limit)

    def _vector_peek_candidates_coll(self, coll: Any, limit: int) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Единый helper для dream-candidates.
        Возвращает (docs, metas) одинаковой длины.
        """
        lim = max(1, int(limit))

        docs2: List[str] = []
        metas2: List[Dict[str, Any]] = []
        seen = set()

        def _ingest(res: Dict[str, Any]) -> None:
            nonlocal docs2, metas2, seen
            docs = res.get("documents") or []
            metas = res.get("metadatas") or []
            for i, d in enumerate(docs):
                if not d:
                    continue
                s = str(d)
                if not s or s in seen:
                    continue
                seen.add(s)
                docs2.append(s)
                m: Dict[str, Any] = {}
                if isinstance(metas, list) and i < len(metas) and isinstance(metas[i], dict):
                    m = dict(metas[i])
                metas2.append(m)
                if len(docs2) >= lim:
                    return

        try:
            total = 0
            try:
                total = int(coll.count())
            except Exception:
                total = 0

            # Mixed windows: head + tail + rotating offsets.
            # This avoids sticking to the same old source when collection head is imbalanced.
            if total > 0:
                windows = 4
                chunk = max(8, min(lim, int(math.ceil(float(lim) / float(windows)))))
                max_off = max(0, total - chunk)
                seed = int(_safe_now_ts() // 1800) + int(total % 9973)
                rnd = random.Random(seed)
                offsets: List[int] = [0]
                if max_off > 0:
                    offsets.append(max_off)
                for _ in range(max(0, windows - len(offsets))):
                    if max_off <= 0:
                        break
                    offsets.append(rnd.randint(0, max_off))

                # dedupe offsets preserving order
                uniq_offsets: List[int] = []
                off_seen = set()
                for o in offsets:
                    oi = int(max(0, o))
                    if oi in off_seen:
                        continue
                    off_seen.add(oi)
                    uniq_offsets.append(oi)

                for off in uniq_offsets:
                    if len(docs2) >= lim:
                        break
                    try:
                        res = coll.get(
                            limit=max(1, int(chunk)),
                            offset=int(off),
                            include=["documents", "metadatas"],
                        )
                        _ingest(res or {})
                    except Exception:
                        continue

            if docs2:
                return (docs2[:lim], metas2[:lim])

            # Fallback for older clients/backends.
            res = coll.peek(limit=lim)
            _ingest(res or {})
            return (docs2[:lim], metas2[:lim])
        except Exception:
            return ([], [])

    def _dream_source_key(self, meta: Optional[Dict[str, Any]]) -> str:
        src = str((meta or {}).get("source") or "").strip()
        if not src:
            return ""
        # Normalize long/variable source strings so the key stays stable.
        src = src.replace("\\", "/").lower()
        if len(src) > 240:
            src = src[-240:]
        return src

    def _dream_source_recent_counts(self, window_sec: int) -> Dict[str, int]:
        out: Dict[str, int] = {}
        try:
            w = max(1, int(window_sec))
        except Exception:
            w = 1
        now_ts = float(_safe_now_ts())
        cutoff = now_ts - float(w)
        with self._lock:
            dq = self._dream_source_recent
            while dq and float(dq[0][0]) < cutoff:
                dq.popleft()
            for _, src in dq:
                if not src:
                    continue
                out[src] = int(out.get(src, 0)) + 1
        return out

    def _remember_dream_context_sources(self, source_counts: Dict[str, int]) -> None:
        if not source_counts:
            return
        now_ts = float(_safe_now_ts())
        with self._lock:
            for src, cnt in (source_counts or {}).items():
                s = str(src or "").strip()
                if not s:
                    continue
                n = max(1, int(cnt or 1))
                for _ in range(n):
                    self._dream_source_recent.append((now_ts, s))


    def build_dream_context(
        self,
        allowed_types: List[str],
        candidates: int,
        tries: int,
        items: int,
        max_chars: int,
        fallback_chat_key: Optional[Tuple[int, int]] = None,
    ) -> str:
        """
        Собирает "пачку" воспоминаний для сна из ГЛОБАЛЬНОЙ памяти.
        Если глобалка пуста - может взять из админ-чата (fallback_chat_key),
        НЕ смешивая коллекции (chat_* остаётся chat_*).
        """
        items = max(1, int(items))
        max_chars = max(2000, int(max_chars))
        candidates = max(1, int(candidates))
        tries = max(1, int(tries))

        allowed = set([str(x).strip() for x in (allowed_types or []) if str(x).strip()])

        picked: List[str] = []
        seen = set()
        source_limits_enabled = bool(DREAM_SOURCE_DIVERSITY)
        source_cap = max(1, int(DREAM_SOURCE_MAX_PER_CONTEXT))
        source_recent_window = max(60, int(DREAM_SOURCE_RECENT_WINDOW_SEC))
        source_recent_cap = max(1, int(DREAM_SOURCE_RECENT_MAX))
        source_counts: Dict[str, int] = {}
        source_recent_counts: Dict[str, int] = (
            self._dream_source_recent_counts(source_recent_window) if source_limits_enabled else {}
        )
        source_phases: Tuple[int, ...]
        if source_limits_enabled:
            source_phases = (0, 1, 2) if DREAM_SOURCE_RELAX_IF_STARVED else (0,)
        else:
            source_phases = (2,)

        def _ok_type(meta: Dict[str, Any]) -> bool:
            if not allowed:
                return True
            t = str((meta or {}).get("type") or "").strip()
            return (t in allowed)

        def _source_key(meta: Dict[str, Any]) -> str:
            if not source_limits_enabled:
                return ""
            return self._dream_source_key(meta)

        def _source_allowed(meta: Dict[str, Any], phase: int) -> bool:
            if not source_limits_enabled:
                return True
            src = _source_key(meta)
            if not src:
                return True
            cur = int(source_counts.get(src, 0))
            # phase=0: per-context cap + recent-window cap
            # phase=1: keep per-context cap only
            # phase=2: emergency fill (no source caps)
            if phase <= 1 and cur >= source_cap:
                return False
            if phase == 0:
                recent = int(source_recent_counts.get(src, 0))
                if (recent + cur) >= source_recent_cap:
                    return False
            return True

        def _source_mark(meta: Dict[str, Any]) -> None:
            if not source_limits_enabled:
                return
            src = _source_key(meta)
            if not src:
                return
            source_counts[src] = int(source_counts.get(src, 0)) + 1

        def _add_docs(docs: List[str], metas: List[Dict[str, Any]]) -> None:
            nonlocal picked, seen
            for i, d in enumerate(docs or []):
                if not d:
                    continue
                s = str(d).strip()
                if not s:
                    continue
                meta = {}
                if isinstance(metas, list) and i < len(metas) and isinstance(metas[i], dict):
                    meta = metas[i]
                if not _ok_type(meta):
                    continue
                if not _source_allowed(meta, phase=2):
                    continue
                k = s
                if k in seen:
                    continue
                seen.add(k)
                picked.append(s)
                _source_mark(meta)
                if len(picked) >= items:
                    return

        def _stable_pick_order(n: int, salt: int) -> List[int]:
            """
            Детерминированное перемешивание индексов:
            - одинаково в пределах короткого окна,
            - но меняется со временем (чтобы сны не были одним и тем же).
            """
            if n <= 0:
                return []
            seed = int(_safe_now_ts() // 1800) + int(salt)  # окно 30 минут
            rnd = random.Random(seed)
            idxs = list(range(n))
            rnd.shuffle(idxs)
            return idxs

        def _select_from_vector_global() -> bool:
            if not (self.vector_ready and self.global_coll is not None):
                return False
            docs, metas = self._vector_peek_candidates_global(limit=candidates)
            if not docs:
                return False

            # Сначала strict-diversity, затем мягкое ослабление, и только потом emergency fill.
            for phase in source_phases:
                if len(picked) >= items:
                    break
                for t in range(tries):
                    order = _stable_pick_order(len(docs), salt=1000 + (phase * 100) + t)
                    for i in order:
                        if len(picked) >= items:
                            break
                        d = docs[i] if i < len(docs) else None
                        m = metas[i] if i < len(metas) else {}
                        if not d:
                            continue
                        s = str(d).strip()
                        if not s or s in seen:
                            continue
                        if not _ok_type(m):
                            continue
                        if not _source_allowed(m, phase=phase):
                            continue
                        seen.add(s)
                        picked.append(s)
                        _source_mark(m)
                    if len(picked) >= items:
                        break

            return bool(picked)

        def _select_from_vector_chat(key: Tuple[int, int]) -> bool:
            if not self.vector_ready:
                return False
            try:
                chat_id, user_id = int(key[0]), int(key[1])
            except Exception:
                return False

            docs, metas = self._vector_peek_candidates_chat(chat_id=chat_id, user_id=user_id, limit=candidates)
            if not docs:
                return False

            for phase in source_phases:
                if len(picked) >= items:
                    break
                for t in range(tries):
                    order = _stable_pick_order(len(docs), salt=2000 + (phase * 100) + t)
                    for i in order:
                        if len(picked) >= items:
                            break
                        d = docs[i] if i < len(docs) else None
                        m = metas[i] if i < len(metas) else {}
                        if not d:
                            continue
                        s = str(d).strip()
                        if not s or s in seen:
                            continue
                        if not _ok_type(m):
                            continue
                        if not _source_allowed(m, phase=phase):
                            continue
                        seen.add(s)
                        picked.append(s)
                        _source_mark(m)
                    if len(picked) >= items:
                        break

            return bool(picked)

        def _select_from_ram_global() -> bool:
            l = list(self._fallback_memory_global or [])
            if not l:
                return False
            # берём хвост как "свежее"
            tail = l[-max(items * 4, candidates):]
            _add_docs(tail, [{} for _ in tail])
            return bool(picked)

        def _select_from_ram_chat(key: Tuple[int, int]) -> bool:
            try:
                k = (int(key[0]), int(key[1]))
            except Exception:
                return False
            memq = self._fallback_memory_chat.get(k)
            if not memq:
                return False
            l = list(memq)
            tail = l[-max(items * 4, candidates):]
            _add_docs(tail, [{} for _ in tail])
            return bool(picked)

        # 1) основной источник — глобальная vector-память
        _ = _select_from_vector_global()

        # 2) fallback на chat-коллекцию (если глобалка пуста / не хватило)
        if len(picked) < items and fallback_chat_key is not None:
            _ = _select_from_vector_chat(fallback_chat_key)

        # 3) если vector не дал ничего — fallback на RAM (global)
        if len(picked) < 1:
            _ = _select_from_ram_global()

        # 4) если и RAM global пуст — пробуем RAM chat (если дали ключ)
        if len(picked) < 1 and fallback_chat_key is not None:
            _ = _select_from_ram_chat(fallback_chat_key)

        if not picked:
            return ""

        if source_limits_enabled and source_counts:
            try:
                self._remember_dream_context_sources(source_counts)
            except Exception:
                pass

        out = "\n\n".join(picked[:items]).strip()
        return truncate_text(out, int(max_chars))


        # 1) Global vector
        if self.vector_ready and self.global_coll is not None:
            docs, metas = self._vector_peek_candidates_global(max(50, int(candidates)))
            if docs:
                # "smart" deterministic permutation:
                # okno 30 minut -> raznoobrazie, no bez khaosa i bez drebezga
                seed_base = int(_safe_now_ts() // 1800)
                idxs = list(range(len(docs)))

                for attempt in range(max(1, int(tries))):
                    rnd = random.Random(seed_base + 1000 + attempt)
                    rnd.shuffle(idxs)

                    # a) prefer allowed types + not junk
                    if allowed:
                        for i in idxs:
                            if len(picked) >= items:
                                break
                            d = docs[i]
                            if not d:
                                continue
                            if _looks_like_technical_junk(d):
                                continue

                            m = {}
                            if isinstance(metas, list) and i < len(metas) and isinstance(metas[i], dict):
                                m = metas[i]

                            t = str((m or {}).get("type", "")).strip()
                            if t and t in allowed:
                                s = str(d).strip()
                                if s and s not in seen:
                                    seen.add(s)
                                    picked.append(s)

                    # b) fallback: non-junk
                    if len(picked) < items:
                        for i in idxs:
                            if len(picked) >= items:
                                break
                            d = docs[i]
                            if not d:
                                continue
                            if _looks_like_technical_junk(d):
                                continue

                            s = str(d).strip()
                            if not s or s in seen:
                                continue
                            seen.add(s)
                            picked.append(s)

                    if len(picked) >= items:
                        break


        # 2) Global fallback memory (non-vector) - includes LEGACY files content
        if len(picked) < items and self._fallback_memory_global:
            mem_list = list(self._fallback_memory_global)

            # we don’t chase the entire list if it’s huge: we take a fresh tail
            tail_cap = max(200, int(candidates) * 8)
            if len(mem_list) > tail_cap:
                mem_list = mem_list[-tail_cap:]

            seed_base = int(_safe_now_ts() // 1800)  # okno 30 minut
            idxs = list(range(len(mem_list)))

            for attempt in range(max(1, int(tries))):
                rnd = random.Random(seed_base + 2000 + attempt)
                rnd.shuffle(idxs)

                # a) prefer non-junk
                for i in idxs:
                    if len(picked) >= items:
                        break
                    d = mem_list[i]
                    if not d:
                        continue
                    if _looks_like_technical_junk(d):
                        continue
                    s = str(d).strip()
                    if not s or s in seen:
                        continue
                    seen.add(s)
                    picked.append(s)

                # b) fallback: any (even if "junk") — no vse ravno bez dubley
                if len(picked) < items:
                    for i in idxs:
                        if len(picked) >= items:
                            break
                        d = mem_list[i]
                        if not d:
                            continue
                        s = str(d).strip()
                        if not s or s in seen:
                            continue
                        seen.add(s)
                        picked.append(s)

                if len(picked) >= items:
                    break


        # 3) Fallback to admin chat memory (only if still nothing meaningful)
        if (not picked or all(_looks_like_technical_junk(x) for x in picked)) and fallback_chat_key:
            chat_id, user_id = fallback_chat_key
            docs, metas = self._vector_peek_candidates_chat(chat_id, user_id, limit=max(80, int(candidates)))
            if docs:
                seed_base = int(_safe_now_ts() // 1800)
                idxs = list(range(len(docs)))

                for attempt in range(max(1, int(tries))):
                    rnd = random.Random(seed_base + 3000 + attempt)
                    rnd.shuffle(idxs)

                    # prefer allowed types if any
                    if allowed:
                        for i in idxs:
                            if len(picked) >= items:
                                break
                            d = docs[i]
                            if not d:
                                continue
                            if _looks_like_technical_junk(d):
                                continue

                            m = {}
                            if isinstance(metas, list) and i < len(metas) and isinstance(metas[i], dict):
                                m = metas[i]

                            t = str((m or {}).get("type", "")).strip()
                            if t and t in allowed:
                                s = str(d).strip()
                                if not s or s in seen:
                                    continue
                                seen.add(s)
                                picked.append(s)

                    # then any non-junk
                    if len(picked) < items:
                        for i in idxs:
                            if len(picked) >= items:
                                break
                            d = docs[i]
                            if not d:
                                continue
                            if _looks_like_technical_junk(d):
                                continue

                            s = str(d).strip()
                            if not s or s in seen:
                                continue
                            seen.add(s)
                            picked.append(s)

                    # last resort: any (still no duplicates)
                    if len(picked) < items:
                        for i in idxs:
                            if len(picked) >= items:
                                break
                            d = docs[i]
                            if not d:
                                continue
                            s = str(d).strip()
                            if not s or s in seen:
                                continue
                            seen.add(s)
                            picked.append(s)

                    if len(picked) >= items:
                        break


        # trim by chars (stable pack)
        out: List[str] = []
        total = 0

        # so that one huge document does not gobble up the entire sleep budget
        per_item_cap = max(300, int(max_chars // max(1, items)) * 3)

        # a small header helps the synthesizer understand that this is a "memory packet"
        header = "DREAM_MEMORY_PACK:\n"
        if len(header) <= max_chars:
            out.append(header)
            total += len(header)

        for i, d in enumerate(picked[:items], start=1):
            s = (str(d) or "").strip()
            if not s:
                continue

            # cut each piece separately
            s = truncate_text(s, per_item_cap)

            chunk = f"[MEM_{i}]\n{s}\n"
            if total + len(chunk) > max_chars:
                break

            out.append(chunk)
            total += len(chunk)

        return "\n".join(out).strip()


    def remember_pending_question(self, chat_id: int, user_id: str, user_name: str, question: str) -> None:
        """Pending question = "questions na potom", kotoryy Ester dolzhna pomnit po chatu.

        YaVNYY MOST: c=a+b -> vopros cheloveka (a) + distsiplina fiksatsii/dedupa (b) => ustoychivoe pending-sostoyanie (c)
        SKRYTYE MOSTY:
          - Cover&Thomas: ekonomiya kanala - rezhem dlinu i ne plodim povtory
          - Ashby: ustoychivost - odinakovyy klyuch (hash) stabiliziruet behavior v raznykh khranilischakh
        ZEMNOY ABZATs: eto kak "list ozhidaniya" u vracha - odna zapis na odnu problemu, a ne 20 odinakovykh talonov."""
        q0 = (question or "").strip()
        if not q0:
            return

        # normalization: no extra spaces/line breaks
        q = re.sub(r"\s+", " ", q0).strip()
        if not q:
            return

        # limit the size of the question (so that one piece does not eat up the entire pending)
        try:
            max_q_chars = int(os.getenv("PENDING_MAX_CHARS", "1600") or 1600)
        except Exception:
            max_q_chars = 1600
        q = truncate_text(q, max_q_chars)

        # stabilnyy khesh = anti-dublikat + stabilnyy ID
        try:
            import hashlib
            qhash = hashlib.sha256(q.lower().encode("utf-8", "ignore")).hexdigest()[:16]
        except Exception:
            qhash = f"{abs(hash(q.lower())):x}"[:16]

        # chat_id safe
        try:
            cid = int(chat_id)
        except Exception:
            cid = 0

        meta = {
            "type": "pending",
            "status": "active",
            "chat_id": str(cid),
            "target_user_id": str(user_id),
            "target_user_name": str(user_name),
            "created": _safe_now_ts(),
            "node": NODE_IDENTITY,
            "qhash": qhash,
        }
        doc = f"PENDING_QUESTION[{qhash}]: {q}"

        # 1) Vector DB: ispolzuem determinirovannyy id -> povtory skhlopyvayutsya
        if self.vector_ready:
            try:
                coll = self._get_pending_coll(cid)
                if coll is not None:
                    _id = f"pending_{cid}_{str(user_id)}_{qhash}"
                    try:
                        coll.add(documents=[doc], metadatas=[meta], ids=[_id])
                    except Exception:
                        # if such an ID already exists, it means it’s a repeat, silently ignore it
                        pass
                    return
            except Exception:
                pass

        # 2) Falbatsk (disc): also a khash dedup
        rec_id = f"pending_{cid}_{str(user_id)}_{qhash}"
        rec = {"id": rec_id, "text": doc, "meta": meta}

        if cid not in self._fallback_pending:
            self._fallback_pending[cid] = []

        # dedup: if it already exists, don’t add it (and don’t touch the disk)
        lst = self._fallback_pending[cid]
        for x in reversed(lst[-200:]):
            try:
                mh = ((x or {}).get("meta") or {}).get("qhash")
                if mh == qhash:
                    return
            except Exception:
                pass

        lst.append(rec)
        self._fallback_pending[cid] = lst[-200:]
        self._save_pending_fallback()


    def get_active_questions(self, chat_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            cid = int(chat_id)
        except Exception:
            cid = 0

        try:
            lim = max(1, int(limit))
        except Exception:
            lim = 5

        def _clean_text(doc: str) -> str:
            s = (doc or "").strip()
            # PENDING_QUESTION[abcd1234]: vopros...
            s = re.sub(r"^PENDING_QUESTION(?:\[[0-9a-fA-F]+\])?:\s*", "", s).strip()
            return s

        def _extract_qhash(doc: str, meta: Dict[str, Any]) -> str:
            qh = ""
            try:
                qh = str((meta or {}).get("qhash") or "").strip()
            except Exception:
                qh = ""
            if qh:
                return qh
            try:
                m = re.search(r"PENDING_QUESTION\[(?P<h>[0-9a-fA-F]{6,32})\]", str(doc or ""))
                if m:
                    return (m.group("h") or "").strip()
            except Exception:
                pass
            return ""

        # -----------------------------
        # 1) Vector path (Chroma)
        # -----------------------------
        if self.vector_ready:
            try:
                coll = self._get_pending_coll(cid)
                if coll is not None:
                    # berem s zapasom, potom otsortiruem sami
                    grab = max(lim * 10, 20)

                    try:
                        # if a non-re-filter is supported, we will immediately filter out the active ones
                        res = coll.get(where={"status": "active"}, limit=grab)
                    except Exception:
                        res = coll.get(limit=grab)

                    questions: List[Dict[str, Any]] = []
                    seen_hash = set()

                    docs = (res.get("documents") or []) if isinstance(res, dict) else []
                    metas = (res.get("metadatas") or []) if isinstance(res, dict) else []
                    ids = (res.get("ids") or []) if isinstance(res, dict) else []

                    for i, doc in enumerate(docs):
                        meta = {}
                        if isinstance(metas, list) and i < len(metas) and isinstance(metas[i], dict):
                            meta = metas[i]
                        status = str((meta or {}).get("status") or "")
                        if status != "active":
                            continue

                        qhash = _extract_qhash(str(doc or ""), meta)
                        if qhash and qhash in seen_hash:
                            continue
                        if qhash:
                            seen_hash.add(qhash)

                        # created timestamp for sorting
                        try:
                            created = float((meta or {}).get("created") or 0.0)
                        except Exception:
                            created = 0.0

                        qid = ""
                        if isinstance(ids, list) and i < len(ids):
                            qid = str(ids[i] or "")

                        questions.append({
                            "text": _clean_text(str(doc or "")),
                            "meta": meta or {},
                            "id": qid,
                            "_created": created,
                        })

                    # sortiruem: novye sverkhu
                    questions.sort(key=lambda x: float(x.get("_created") or 0.0), reverse=True)

                    # chistim sluzhebnoe pole
                    out = []
                    for x in questions[:lim]:
                        x.pop("_created", None)
                        out.append(x)
                    return out

            except Exception:
                pass

        # -----------------------------
        # 2) Fallback path (disk/RAM)
        # -----------------------------
        lst = (self._fallback_pending.get(cid) or [])
        if not isinstance(lst, list):
            return []

        act = []
        seen_hash = set()

        # we take from the tail (usually it’s fresher there), but still sort by created
        for x in reversed(lst[-500:]):
            if not isinstance(x, dict):
                continue
            meta = (x.get("meta") or {}) if isinstance(x.get("meta"), dict) else {}
            if str(meta.get("status") or "") != "active":
                continue

            doc = str(x.get("text") or "")
            qhash = _extract_qhash(doc, meta)
            if qhash and qhash in seen_hash:
                continue
            if qhash:
                seen_hash.add(qhash)

            try:
                created = float(meta.get("created") or 0.0)
            except Exception:
                created = 0.0

            act.append({
                "id": str(x.get("id") or ""),
                "text": _clean_text(doc),
                "meta": meta,
                "_created": created,
            })

        act.sort(key=lambda x: float(x.get("_created") or 0.0), reverse=True)

        out = []
        for x in act[:lim]:
            x.pop("_created", None)
            out.append(x)
        return out


    def mark_question_resolved(self, chat_id: int, qid: str) -> None:
        """Pomechaet pending questions as resolved.

        Accept:
        - polnyy qid (for example pending_<chat>_<user>_<qhash>)
        - ili korotkiy qhash (16 hex) - then poprobuem nayti zapis i zakryt ee"""
        qid0 = (qid or "").strip()
        if not qid0:
            return

        try:
            cid = int(chat_id)
        except Exception:
            cid = 0

        now_ts = _safe_now_ts()

        def _is_qhash(s: str) -> bool:
            return bool(re.fullmatch(r"[0-9a-fA-F]{12,32}", (s or "").strip()))

        want_hash = qid0.lower() if _is_qhash(qid0) and len(qid0) <= 32 else ""

        # ============================
        # 1) Vector path (Chroma)
        # ============================
        if self.vector_ready:
            try:
                coll = self._get_pending_coll(cid)
                if coll is not None:

                    def _resolve_doc(_id: str, doc: str, meta: Dict[str, Any]) -> None:
                        meta2 = dict(meta or {})
                        meta2["status"] = "resolved"
                        meta2["resolved"] = now_ts
                        # Chrome update "on the forehead" may not be available -> delete+add
                        try:
                            coll.delete(ids=[_id])
                        except Exception:
                            pass
                        try:
                            coll.add(documents=[doc], metadatas=[meta2], ids=[_id])
                        except Exception:
                            # if the add fails, it’s better to quit silently than to ruin your pulse
                            pass

                    # 1a) pryamoe zakrytie po id
                    try:
                        got = coll.get(ids=[qid0])
                        docs = got.get("documents") or []
                        if docs:
                            doc = str(docs[0] or "")
                            metas = got.get("metadatas") or []
                            meta = (metas[0] if metas and isinstance(metas[0], dict) else {}) or {}
                            _resolve_doc(qid0, doc, meta)
                            return
                    except Exception:
                        pass

                    # 1b) if this is a khash, we will find an entry for khash in the metadata/text
                    if want_hash:
                        try:
                            res = coll.get(limit=500)
                            docs = res.get("documents") or []
                            metas = res.get("metadatas") or []
                            ids = res.get("ids") or []

                            for i, doc in enumerate(docs):
                                meta = {}
                                if isinstance(metas, list) and i < len(metas) and isinstance(metas[i], dict):
                                    meta = metas[i] or {}

                                mh = str((meta or {}).get("qhash") or "").strip().lower()
                                if not mh:
                                    # poprobuem vytaschit iz teksta
                                    try:
                                        m = re.search(r"PENDING_QUESTION\[(?P<h>[0-9a-fA-F]{6,32})\]", str(doc or ""))
                                        if m:
                                            mh = (m.group("h") or "").strip().lower()
                                    except Exception:
                                        mh = ""

                                if mh and mh == want_hash:
                                    _id = str(ids[i] or "") if isinstance(ids, list) and i < len(ids) else ""
                                    if _id:
                                        _resolve_doc(_id, str(doc or ""), meta)
                                        return
                        except Exception:
                            pass

            except Exception:
                pass

        # ============================
        # 2) Fallback path (disk/RAM)
        # ============================
        lst = self._fallback_pending.get(cid) or []
        if not isinstance(lst, list) or not lst:
            return

        changed = False

        # 2a) first by exact ID
        for x in lst:
            if not isinstance(x, dict):
                continue
            if str(x.get("id") or "") == qid0:
                meta = x.get("meta")
                if not isinstance(meta, dict):
                    meta = {}
                    x["meta"] = meta
                meta["status"] = "resolved"
                meta["resolved"] = now_ts
                changed = True

        # 2b) if a khash is passed, we try to close it
        if (not changed) and want_hash:
            for x in lst:
                if not isinstance(x, dict):
                    continue
                meta = x.get("meta")
                if not isinstance(meta, dict):
                    meta = {}

                mh = str(meta.get("qhash") or "").strip().lower()
                if not mh:
                    # extract from text if necessary
                    try:
                        doc = str(x.get("text") or "")
                        m = re.search(r"PENDING_QUESTION\[(?P<h>[0-9a-fA-F]{6,32})\]", doc)
                        if m:
                            mh = (m.group("h") or "").strip().lower()
                    except Exception:
                        mh = ""

                if mh and mh == want_hash:
                    if not isinstance(x.get("meta"), dict):
                        x["meta"] = meta
                    x["meta"]["status"] = "resolved"
                    x["meta"]["resolved"] = now_ts
                    changed = True

        if changed:
            self._fallback_pending[cid] = lst[-200:]
            self._save_pending_fallback()


# --- 13) Volition / Dreams / Curiosity (son fonom; sny lokalno) ---
class VolitionSystem:
    def __init__(self):
        self.last_interaction = _safe_now_ts()
        self.state = "AWAKE"
        self.sleep_threshold = float(SLEEP_THRESHOLD_SEC)
        self.is_thinking = False

        # Curiosity tnrottleles (used in Curiosity/social cycles)
        self.last_question_time = 0.0
        self.min_question_interval = float(CURIOSITY_MIN_INTERVAL_SEC)
        self.last_asked_hash = ""

        # anti-loop
        self._last_cycle_ts = 0.0

        # hard safety: only one background cycle at a time
        self._cycle_lock = asyncio.Lock()
        self._cycle_task = None  # type: Optional[asyncio.Task]

    def init(self) -> None:
        return

    def touch(self) -> None:
        """Any external interaction wakes Esther up.
        If there was a dream in the background, it softly shades it so as not to touch the pulse."""
        self.last_interaction = _safe_now_ts()

        if self.state == "DREAMING":
            self.state = "AWAKE"

        # cancel background dream if still running
        t = self._cycle_task
        if t is not None and not t.done():
            try:
                t.cancel()
                try:
                    _mirror_background_event(
                        "[VOLITION_WAKE] cancel_cycle",
                        "volition",
                        "wake",
                    )
                except Exception:
                    pass
            except Exception:
                pass

    async def life_tick(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """The vice should be very light: no long avait inside.
        Only solution + fire-and-forget."""
        now = _safe_now_ts()
        idle = now - float(self.last_interaction)

        if VOLITION_DEBUG:
            logging.info(f"[VOLITION] tick idle={idle:.1f}s state={self.state} thinking={self.is_thinking}")

        # perekhod v son
        if self.state == "AWAKE" and idle > float(self.sleep_threshold):
            self.state = "DREAMING"
            logging.info("uVOLITIONSch Transition to DREAMING mode (background reflections).")
            try:
                _mirror_background_event(
                    f"[VOLITION_SLEEP] idle={idle:.1f}s",
                    "volition",
                    "sleep",
                )
            except Exception:
                pass

        # If he’s not sleeping, we’ll go out
        if self.state != "DREAMING":
            return

        # if we’re already thinking, let’s go out
        if self.is_thinking:
            return

        # anti-spam tsiklov
        if (now - float(self._last_cycle_ts)) < float(DREAM_MIN_INTERVAL_SEC):
            return

        # startuem tsikl (fire-and-forget)
        self.is_thinking = True
        self._last_cycle_ts = now

        async def _run_cycle_guarded() -> None:
            # single entry into the loop
            async with self._cycle_lock:
                try:
                    # if we were waiting for the shine, we were already woken up
                    if self.state != "DREAMING":
                        return

                    # osnovnoy vybor tsikla
                    if random.random() < float(SOCIAL_PROB):
                        try:
                            _mirror_background_event(
                                "[VOLITION_CYCLE] social_synapse",
                                "volition",
                                "cycle_social",
                            )
                        except Exception:
                            pass
                        await self.social_synapse_cycle(context)
                    else:
                        try:
                            _mirror_background_event(
                                "[VOLITION_CYCLE] dream",
                                "volition",
                                "cycle_dream",
                            )
                        except Exception:
                            pass
                        await self.dream_cycle(context)

                except asyncio.CancelledError:
                    # normal cancellation on touch()
                    if VOLITION_DEBUG:
                        logging.info("[VOLITION] cycle cancelled (touch wake-up).")
                    try:
                        _mirror_background_event(
                            "[VOLITION_CYCLE_CANCELLED]",
                            "volition",
                            "cycle_cancel",
                        )
                    except Exception:
                        pass
                    return
                except Exception as e:
                    logging.warning(f"[VOLITION] cycle crashed: {e}")
                    try:
                        _mirror_background_event(
                            f"[VOLITION_CYCLE_ERROR] {e}",
                            "volition",
                            "cycle_error",
                        )
                    except Exception:
                        pass
                finally:
                    self.is_thinking = False

        try:
            self._cycle_task = asyncio.create_task(_run_cycle_guarded())
        except Exception:
            # if suddenly create_task fell, just release the flag
            self.is_thinking = False
            self._cycle_task = None


    async def _dream_pass_draft(self, synth: str, mem: str) -> str:
        prompt = f"""
DREAM_PASS_1_DRAFT
{ESTER_CORE_SYSTEM_ANCHOR}

Ty v glubokom razmyshlenii. Memory podbrosila fragmenty:

--- MEMORY ---
{truncate_text(mem, DREAM_CONTEXT_CHARS)}
--- /MEMORY ---

ZADAChA (chernovik):
1. Sformuliruy smysl "1–3 abzatsa".
2. Obyazatelno naydi:
   - 2 svyazi/assotsiatsii
   - 1 alternativnuyu traktovku
3. V kontse predlozhi ODIN iz variantov:
   - DRAFT_INSIGHT: ...
   - DRAFT_QUESTION: ...
   - DRAFT_SELF_SEARCH: ...

Pishi yasno, po delu.
""".strip()

        prompt = truncate_text(prompt, DREAM_MAX_PROMPT_CHARS)

        try:
            out = await _safe_chat(
                synth,
                [{"role": "system", "content": prompt}],
                temperature=DREAM_TEMPERATURE,
                max_tokens=DREAM_MAX_TOKENS,
                strict_provider=DREAM_STRICT_LOCAL,
                allow_oracle=DREAM_ALLOW_ORACLE,
            )
            return (out or "").strip()
        except Exception:
            return ""


    async def _dream_pass_critic(self, synth: str, mem: str, draft: str) -> str:
        prompt = f"""
DREAM_PASS_2_CRITIC
{ESTER_CORE_SYSTEM_ANCHOR}

--- MEMORY ---
{truncate_text(mem, DREAM_CONTEXT_CHARS)}
--- /MEMORY ---

--- DRAFT ---
{truncate_text(draft, 8000)}
--- /DRAFT ---

PROVER:
1. Gde slaboe mesto / neobosnovannost?
2. Day 2 alternativy / kontrargumenta.
3. Chto realno utochnit u Owner (esli vazhno)?
4. Gde voda?

Vyvod: verni strogo
CRITIC_NOTES:
- punkt
- punkt
- punkt
""".strip()

        prompt = truncate_text(prompt, DREAM_MAX_PROMPT_CHARS)

        try:
            critic_max = min(3000, int(DREAM_MAX_TOKENS)) if int(DREAM_MAX_TOKENS or 0) > 0 else 1200
        except Exception:
            critic_max = 1200

        try:
            out = await _safe_chat(
                synth,
                [{"role": "system", "content": prompt}],
                temperature=0.2,
                max_tokens=critic_max,
                strict_provider=DREAM_STRICT_LOCAL,
                allow_oracle=DREAM_ALLOW_ORACLE,
            )
            return (out or "").strip()
        except Exception:
            return ""


    async def _dream_pass_final(self, synth: str, mem: str, draft: str, critic: str) -> str:
        prompt = f"""
DREAM_PASS_3_FINAL
{ESTER_CORE_SYSTEM_ANCHOR}

--- MEMORY ---
{truncate_text(mem, DREAM_CONTEXT_CHARS)}
--- /MEMORY ---

--- DRAFT ---
{truncate_text(draft, 12000)}
--- /DRAFT ---

--- CRITIC ---
{truncate_text(critic, 6000)}
--- /CRITIC ---

OBYaZATELNYY FORMAT VYKhODA: TOLKO ODNA STROKA, ODIN VARIANT:

1. [ASK_OWNER] <odin vopros, maksimum 2 predlozheniya>
ILI
2. [INSIGHT] <3-12 predlozheniy, bez poezii>
ILI
3. [SELF_SEARCH] <poiskovyy zapros, 5-12 slov>

Esli mozhno oboytis insaytom - vybiray insayt.
""".strip()

        prompt = truncate_text(prompt, DREAM_MAX_PROMPT_CHARS)

        try:
            final_max = min(4000, int(DREAM_MAX_TOKENS)) if int(DREAM_MAX_TOKENS or 0) > 0 else 1000
        except Exception:
            final_max = 1000

        try:
            out = await _safe_chat(
                synth,
                [{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=final_max,
                strict_provider=DREAM_STRICT_LOCAL,
                allow_oracle=DREAM_ALLOW_ORACLE,
            )
            out = (out or "").strip()

            # --- enforce: ONLY ONE LINE ---
            if out:
                out = out.splitlines()[0].strip()

            # --- enforce: starts with one of allowed tags ---
            if out and not (
                out.startswith("[ASK_OWNER]") or out.startswith("[INSIGHT]") or out.startswith("[SELF_SEARCH]")
            ):
                # soft auto-rollback: if the model “forgot the format” - turn it into INSIGNT in one line
                out = "[INSIGHT] " + out

            return out
        except Exception:
            return ""


    async def dream_cycle(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Explicit BRIDGE: c=a+b -> "memory" (a) + safe background loop (c) => stable sleep (c)
        # HIDDEN BRIDGES: Ashby (limiting diversity through timeouts), Carpet&Thomas (saving channel/context)
        # EARTHLY Paragraph: sleep is like tissue regeneration: it should go in the background and NOT stop the bot’s heartbeat.

        synth = hive.pick_dream_synth()

        fb = None
        global LAST_ADMIN_CHAT_KEY
        if DREAM_FALLBACK_ADMIN_CHAT and LAST_ADMIN_CHAT_KEY:
            fb = LAST_ADMIN_CHAT_KEY

        # Sleep pass timeouts (so as not to freeze)
        try:
            pass1_timeout = float(os.getenv("DREAM_PASS1_TIMEOUT_SEC", "180") or 180.0)
        except Exception:
            pass1_timeout = 180.0

        try:
            pass2_timeout = float(os.getenv("DREAM_PASS2_TIMEOUT_SEC", "120") or 120.0)
        except Exception:
            pass2_timeout = 120.0

        try:
            pass3_timeout = float(os.getenv("DREAM_PASS3_TIMEOUT_SEC", "120") or 120.0)
        except Exception:
            pass3_timeout = 120.0

        # 1) Sobiraem pamyat V FONE (ne trogaem puls)
        try:
            mem = await asyncio.to_thread(
                brain.build_dream_context,
                allowed_types=DREAM_ALLOWED_TYPES,
                candidates=DREAM_MEMORY_CANDIDATES,
                tries=DREAM_MEMORY_TRIES,
                items=DREAM_CONTEXT_ITEMS,
                max_chars=DREAM_CONTEXT_CHARS,
                fallback_chat_key=fb,
            )
        except Exception as e:
            logging.warning(f"[DREAM] build_dream_context failed: {e}")
            try:
                _mirror_background_event(
                    f"[DREAM_CONTEXT_ERROR] {e}",
                    "dream",
                    "context_error",
                )
            except Exception:
                pass
            return

        if not mem:
            logging.info(">>> uVOLITIONsch There are no suitable memories for sleep (even after bootstrap/falseback).")
            logging.info(">>> uVOLITIONsch Hint: send any document or /seed <text> (Ovner only) - and the dream will come to life.")
            try:
                _mirror_background_event(
                    "[DREAM_NO_CONTEXT]",
                    "dream",
                    "no_context",
                )
            except Exception:
                pass
            return

        logging.info(f"[DREAM] cycle start provider={synth} ctx_items={DREAM_CONTEXT_ITEMS} mem_chars={len(mem)}")
        try:
            _mirror_background_event(
                f"[DREAM_START] provider={synth} mem_chars={len(mem)}",
                "dream",
                "start",
            )
        except Exception:
            pass

        # 2) PASS 1 — DRAFT
        try:
            draft = await asyncio.wait_for(self._dream_pass_draft(synth, mem), timeout=max(5.0, pass1_timeout))
        except asyncio.TimeoutError:
            logging.warning(f"[DREAM] pass1 timeout (provider={synth}).")
            try:
                _mirror_background_event(
                    f"[DREAM_PASS1_TIMEOUT] provider={synth}",
                    "dream",
                    "pass1_timeout",
                )
            except Exception:
                pass
            return
        except Exception as e:
            logging.warning(f"[DREAM] pass1 failed (provider={synth}): {e}")
            try:
                _mirror_background_event(
                    f"[DREAM_PASS1_ERROR] provider={synth} err={e}",
                    "dream",
                    "pass1_error",
                )
            except Exception:
                pass
            return

        draft = (draft or "").strip()
        if not draft:
            logging.warning(f"[DREAM] pass1 empty (provider={synth}). Prover LM Studio / model / max output tokens.")
            try:
                _mirror_background_event(
                    f"[DREAM_PASS1_EMPTY] provider={synth}",
                    "dream",
                    "pass1_empty",
                )
            except Exception:
                pass
            return

        # 3) PASS 2/3 — CRITIC + FINAL
        critic = "CRITIC_NOTES: (skipped)"
        final = ""

        if int(DREAM_PASSES) <= 1:
            # srazu final
            try:
                final = await asyncio.wait_for(
                    self._dream_pass_final(synth, mem, draft, critic),
                    timeout=max(5.0, pass3_timeout),
                )
            except asyncio.TimeoutError:
                logging.warning(f"[DREAM] final timeout (provider={synth}).")
                try:
                    _mirror_background_event(
                        f"[DREAM_FINAL_TIMEOUT] provider={synth}",
                        "dream",
                        "final_timeout",
                    )
                except Exception:
                    pass
                return
            except Exception as e:
                logging.warning(f"[DREAM] final failed (provider={synth}): {e}")
                try:
                    _mirror_background_event(
                        f"[DREAM_FINAL_ERROR] provider={synth} err={e}",
                        "dream",
                        "final_error",
                    )
                except Exception:
                    pass
                return
        else:
            # critic
            if int(DREAM_PASSES) >= 2:
                try:
                    critic = await asyncio.wait_for(
                        self._dream_pass_critic(synth, mem, draft),
                        timeout=max(5.0, pass2_timeout),
                    )
                except asyncio.TimeoutError:
                    logging.warning(f"[DREAM] pass2 timeout (provider={synth}).")
                    try:
                        _mirror_background_event(
                            f"[DREAM_PASS2_TIMEOUT] provider={synth}",
                            "dream",
                            "pass2_timeout",
                        )
                    except Exception:
                        pass
                    critic = "CRITIC_NOTES: (timeout)"
                except Exception as e:
                    logging.warning(f"[DREAM] pass2 failed (provider={synth}): {e}")
                    try:
                        _mirror_background_event(
                            f"[DREAM_PASS2_ERROR] provider={synth} err={e}",
                            "dream",
                            "pass2_error",
                        )
                    except Exception:
                        pass
                    critic = "CRITIC_NOTES: (failed)"

            # final
            if int(DREAM_PASSES) >= 3:
                try:
                    final = await asyncio.wait_for(
                        self._dream_pass_final(synth, mem, draft, critic),
                        timeout=max(5.0, pass3_timeout),
                    )
                except asyncio.TimeoutError:
                    logging.warning(f"[DREAM] pass3 timeout (provider={synth}).")
                    try:
                        _mirror_background_event(
                            f"[DREAM_PASS3_TIMEOUT] provider={synth}",
                            "dream",
                            "pass3_timeout",
                        )
                    except Exception:
                        pass
                    return
                except Exception as e:
                    logging.warning(f"[DREAM] pass3 failed (provider={synth}): {e}")
                    try:
                        _mirror_background_event(
                            f"[DREAM_PASS3_ERROR] provider={synth} err={e}",
                            "dream",
                            "pass3_error",
                        )
                    except Exception:
                        pass
                    return
            else:
                final = draft

        final = (final or "").strip()
        if not final:
            logging.warning(f"[DREAM] final empty (provider={synth}).")
            try:
                _mirror_background_event(
                    f"[DREAM_FINAL_EMPTY] provider={synth}",
                    "dream",
                    "final_empty",
                )
            except Exception:
                pass
            return

        # 4) (optional) remember in memory as “dream” (not necessary, but useful)
        try:
            brain.remember_fact(
                text=f"[DREAM_RESULT] {final}",
                source="dream",
                meta={"type": "dream", "scope": "global"},
            )
        except Exception:
            pass
        try:
            _mirror_background_event(f"[DREAM_RESULT] {final}", "dream", "dream")
        except Exception:
            pass

        logging.info(f"[DREAM] cycle done provider={synth}: {final[:120]}...")


        tag = "INSIGHT"
        payload = (final or "").strip()

        # First, a strict format (as you require: one line with a prefix)
        if payload.startswith("[ASK_OWNER]"):
            tag = "ASK_OWNER"
            payload = payload[len("[ASK_OWNER]"):].strip()
        elif payload.startswith("[SELF_SEARCH]"):
            tag = "SELF_SEARCH"
            payload = payload[len("[SELF_SEARCH]"):].strip()
        elif payload.startswith("[INSIGHT]"):
            tag = "INSIGHT"
            payload = payload[len("[INSIGHT]"):].strip()
        else:
            # false: if the model suddenly inserted the tag not at the beginning
            if "[ASK_OWNER]" in payload:
                tag = "ASK_OWNER"
                payload = payload.split("[ASK_OWNER]", 1)[1].strip()
            elif "[SELF_SEARCH]" in payload:
                tag = "SELF_SEARCH"
                payload = payload.split("[SELF_SEARCH]", 1)[1].strip()
            elif "[INSIGHT]" in payload:
                tag = "INSIGHT"
                payload = payload.split("[INSIGHT]", 1)[1].strip()

        if not payload:
            return

        # Saves memory/logs a little from huge sheets
        payload = truncate_text(payload, 4000)

        if tag == "ASK_OWNER":
            if not ADMIN_ID:
                brain.remember_fact(
                    f"DREAM_ASK_SKIPPED(no_admin): {payload}",
                    source="dream",
                    meta={"type": "dream_question", "scope": "global"},
                )
                return


            # 1) time-locked - first
            is_time_ok = (_safe_now_ts() - self.last_question_time > self.min_question_interval)
            if not is_time_ok:
                brain.remember_fact(
                    f"DREAM_ASK_DEFERRED(cooldown): {payload}",
                    source="dream",
                    meta={"type": "dream_question", "scope": "global"},
                )
                return

            try:
                # --- CTXQ START ---
                try:
                    if CTXQ_ENGINE and str(os.getenv("ESTER_CTXQ_ENABLED", "1")).lower() not in ("0","false","off"):
                        try:
                            from zoneinfo import ZoneInfo
                            _dt = datetime.datetime.fromtimestamp(_safe_now_ts(), tz=ZoneInfo("UTC"))
                        except Exception:
                            _dt = datetime.datetime.now()

                        _hist = []
                        try:
                            _hist = short_term_by_key(str(ADMIN_ID))[-80:]
                        except Exception:
                            pass

                        _inp = CtxqInput(
                            now=_dt,
                            history=_hist,
                            internal_state={"node": NODE_IDENTITY},
                            recalled=[],
                            user_profile={"birthdate": os.getenv("ESTER_USER_BIRTHDATE", "")},
                        )
                        payload, _ = CTXQ_ENGINE.refine_or_replace(payload, _inp)
                except Exception:
                    pass
                # --- CTXQ END ---

                # 2) duplicate the hash AFTER the refinement (and actually according to the hash)
                import hashlib

                def _payload_fingerprint(s: str) -> str:
                    s = (s or "").strip().lower()
                    s = re.sub(r"\s+", " ", s)
                    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

                fp = _payload_fingerprint(payload)
                is_duplicate = (fp == (self.last_asked_hash or ""))

                if is_duplicate:
                    brain.remember_fact(
                        f"DREAM_ASK_DEFERRED(dup): {payload}",
                        source="dream",
                        meta={"type": "dream_question", "scope": "global"},
                    )
                    return

                await context.bot.send_message(
                    chat_id=int(ADMIN_ID),
                    text=f"✨ Mysl prishla… {payload}"
                )

                self.last_question_time = _safe_now_ts()
                self.last_asked_hash = fp

            except Exception as e:
                logging.warning(f"[DREAM] send ASK_OWNER failed: {e}")

            finally:
                brain.remember_fact(
                    f"DREAM_QUESTION: {payload}\n\nMEM:\n{truncate_text(mem, 3000)}\n\nDRAFT:\n{truncate_text(draft, 2000)}",
                    source="dream",
                    meta={"type": "dream_question", "scope": "global"},
                )

            return


        if tag == "SELF_SEARCH":
            import hashlib

            query = (payload or "").strip()
            if not query:
                return

            # --- anti-spam for self-search (separate from ASK_OVNER) ---
            def _fingerprint(s: str) -> str:
                s = (s or "").strip().lower()
                s = re.sub(r"\s+", " ", s)
                return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

            # init dynamically (without rewriting __init__)
            if not hasattr(self, "last_self_search_time"):
                self.last_self_search_time = 0.0
            if not hasattr(self, "last_self_search_hash"):
                self.last_self_search_hash = ""

            try:
                cooldown = float(os.getenv("DREAM_SELF_SEARCH_COOLDOWN_SEC", "90") or 90.0)
            except Exception:
                cooldown = 90.0

            now_ts = _safe_now_ts()
            fp = _fingerprint(query)

            if (now_ts - float(self.last_self_search_time)) < cooldown or fp == (self.last_self_search_hash or ""):
                brain.remember_fact(
                    f"DREAM_SELF_SEARCH_DEFERRED(cooldown_or_dup): {query}",
                    source="dream",
                    meta={"type": "self_search", "scope": "global"},
                )
                return

            # zakrytyy boks / net veba
            if CLOSED_BOX or not WEB_AVAILABLE:
                brain.remember_fact(
                    f"DREAM_SELF_SEARCH_SKIPPED: {query}",
                    source="dream",
                    meta={"type": "self_search", "scope": "global"},
                )
                _curiosity_open_ticket_safe(
                    query,
                    source="low_confidence",
                    context_text="dream_self_search_blocked",
                    recall_score=None,
                )
                self.last_self_search_time = now_ts
                self.last_self_search_hash = fp
                return

            # delaem poisk
            try:
                web = await get_web_evidence_async(query, 3)
            except Exception:
                web = ""

            web = (web or "").strip()

            if web:
                brain.remember_fact(
                    f"Self-Research: {query}\n{truncate_text(web, 6000)}",
                    source="autonomy",
                    meta={"type": "self_search", "scope": "global"},
                )
                try:
                    _mirror_background_event(
                        f"[WEB_AUTONOMY] {query}\n{truncate_text(web, 6000)}",
                        "autonomy",
                        "web_autonomy",
                    )
                except Exception:
                    pass
            else:
                brain.remember_fact(
                    f"Self-Research(empty): {query}",
                    source="autonomy",
                    meta={"type": "self_search", "scope": "global"},
                )
                try:
                    _mirror_background_event(f"[WEB_AUTONOMY_EMPTY] {query}", "autonomy", "web_autonomy")
                except Exception:
                    pass

            # fiksiruem anti-spam markery
            self.last_self_search_time = now_ts
            self.last_self_search_hash = fp
            return


async def social_synapse_cycle(self, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sotsialnyy tsikl: vybiraem odnu aktivnuyu pending-voprosinu i myagko sprashivaem v chate.
    Uluchsheniya:
    - ne "promakhivaemsya": try neskolko chatov, poka ne naydem zadachi
    - anti-spam: cooldown + zaschita ot dubley
    - after uspeshnoy otpravki pomechaem questions resolved"""
    import hashlib
    import html

    # --- anti-spam (lenivo i bezopasno, bez pravki __init__) ---
    if not hasattr(self, "_last_social_ts"):
        self._last_social_ts = 0.0
    if not hasattr(self, "_last_social_hash"):
        self._last_social_hash = ""

    try:
        cooldown = float(os.getenv("SOCIAL_SYNAPSE_COOLDOWN_SEC", "120") or 120.0)
    except Exception:
        cooldown = 120.0

    now_ts = _safe_now_ts()
    if (now_ts - float(self._last_social_ts)) < cooldown:
        return

    # --- 1) kandidaty chatov iz pending (fallback) ---
    pending = getattr(brain, "_fallback_pending", None)
    if not isinstance(pending, dict) or not pending:
        return

    candidate_chats: List[int] = []
    try:
        for k in pending.keys():
            try:
                cid = int(k)
                if cid != 0:
                    candidate_chats.append(cid)
            except Exception:
                pass
    except Exception:
        candidate_chats = []

    if not candidate_chats:
        return

    # --- 2) don’t miss: we are looking for a chat with real tasks ---
    random.shuffle(candidate_chats)

    tasks: List[Dict[str, Any]] = []
    chat_id = None

    tries = min(6, len(candidate_chats))
    for i in range(tries):
        cid = candidate_chats[i]
        t = brain.get_active_questions(chat_id=cid, limit=3)
        if t:
            chat_id = cid
            tasks = t
            break

    if not tasks or chat_id is None:
        return

    # --- 3) take the task ---
    task = random.choice(tasks)
    qid = str(task.get("id") or "").strip()

    query_text = str(task.get("text", "") or "").replace("PENDING_QUESTION: ", "").strip()
    meta = task.get("meta") or {}

    target_user_id = meta.get("target_user_id")
    target_user_name = str(meta.get("target_user_name", "user") or "user").strip()

    if not query_text or not target_user_id:
        # difficult task - so as not to spin endlessly
        if qid:
            try:
                brain.mark_question_resolved(chat_id=int(chat_id), qid=qid)
            except Exception:
                pass
        return

    # --- 4) anti-dublikat po soderzhaniyu ---
    def _fp(s: str) -> str:
        s = (s or "").strip().lower()
        s = re.sub(r"\s+", " ", s)
        return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

    fp = _fp(f"{chat_id}|{target_user_id}|{query_text}")
    if fp == (self._last_social_hash or ""):
        return

    # --- 5) send the question to the same chat ---
    try:
        uid_int = int(str(target_user_id))
    except Exception:
        uid_int = None

    if uid_int:
        mention = f'<a href="tg://user?id={uid_int}">{html.escape(target_user_name)}</a>'
    else:
        mention = html.escape(target_user_name)

    msg = f"🤝 {mention}, vopros ot Ester:\n{html.escape(query_text)}"

    try:
        await context.bot.send_message(
            chat_id=int(chat_id),
            text=msg,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        # anti-spam fiksatsiya
        self._last_social_ts = now_ts
        self._last_social_hash = fp

        # mark the task completed
        if qid:
            try:
                brain.mark_question_resolved(chat_id=int(chat_id), qid=qid)
            except Exception:
                pass

        # log v pamyat (globalno)
        brain.remember_fact(
            f"SOCIAL_ASK(chat={chat_id}, user={target_user_id}): {query_text}",
            source="volition",
            meta={"type": "social_synapse", "scope": "global"},
        )
        try:
            _mirror_background_event(
                f"[SOCIAL_ASK] chat={chat_id} user={target_user_id}: {query_text}",
                "volition",
                "social_synapse",
            )
        except Exception:
            pass

    except Exception as e:
        # if it doesn’t work, don’t spam with attempts forever
        brain.remember_fact(
            f"SOCIAL_ASK_FAILED(chat={chat_id}, user={target_user_id}): {query_text}\nERR: {e}",
            source="volition",
            meta={"type": "social_synapse_fail", "scope": "global"},
        )
        try:
            _mirror_background_event(
                f"[SOCIAL_ASK_FAILED] chat={chat_id} user={target_user_id}: {query_text} | ERR: {e}",
                "volition",
                "social_synapse_fail",
            )
        except Exception:
            pass
        if qid:
            try:
                brain.mark_question_resolved(chat_id=int(chat_id), qid=qid)
            except Exception:
                pass
        return


        try:
            tid = int(str(target_user_id))
        except Exception:
            tid = None

        knowledge = ""
        if tid is not None:
            try:
                knowledge = brain.recall(
                    query_text,
                    chat_id=int(chat_id),
                    user_id=int(tid),
                    n=5,
                    include_global=True
                )
            except Exception:
                knowledge = ""

        knowledge = (knowledge or "").strip()
        if len(knowledge) < 20:
            return

        # Cheap verification: default locale (EU/NO should not burn cloud tokens)
        check_provider = (os.getenv("SOCIAL_CHECK_PROVIDER", "local") or "local").strip().lower()
        if not (PROVIDERS.has(check_provider) and PROVIDERS.enabled(check_provider)):
            check_provider = hive.pick_reply_synth()

        check_prompt = f"""
SYSTEM: SOCIAL_CHECK.
{ESTER_CORE_SYSTEM_ANCHOR}

Vopros ot {target_user_name}: "{truncate_text(query_text, 400)}"

Naydennyy kontekst (pamyat):
{truncate_text(knowledge, 1500)}

Est li zdes pryamoy otvet na vopros?
Otvet strogo odnim slovom: YES ili NO.
""".strip()

        chk = await _safe_chat(
            check_provider,
            [{"role": "system", "content": truncate_text(check_prompt, 6000)}],
            temperature=0.0,
            max_tokens=8
        )

        if "YES" not in (chk or "").strip().upper():
            return


        answer_provider = (os.getenv("SOCIAL_ANSWER_PROVIDER", "local") or "local").strip().lower()
        if not (PROVIDERS.has(answer_provider) and PROVIDERS.enabled(answer_provider)):
            answer_provider = synth  # fallback na tekuschiy synth

        answer_prompt = f"""
SYSTEM: SOCIAL_ANSWER.
{ESTER_CORE_SYSTEM_ANCHOR}

Ty nashla otvet na staryy vopros polzovatelya {target_user_name}: "{truncate_text(query_text, 600)}".

Napishi emu korotko i po delu.
Ispolzuy TOLKO fakty iz konteksta nizhe. Nichego ne vydumyvay.

FAKTY/KONTEKST:
{truncate_text(knowledge, 2000)}
""".strip()

        final_msg = await _safe_chat(
            answer_provider,
            [{"role": "system", "content": truncate_text(answer_prompt, 6000)}],
            temperature=0.6,
            max_tokens=800
        )

        final_msg = (final_msg or "").strip()
        if not final_msg:
            return

        try:
            await context.bot.send_message(
                chat_id=int(target_user_id),
                text=truncate_text(final_msg, 4000)
            )

            qid = str(task.get("id") or "").strip()
            if qid:
                brain.mark_question_resolved(chat_id=int(chat_id), qid=qid)

        except Exception as e:
            try:
                logging.warning(f"[SOCIAL] send/resolve failed: {e}")
            except Exception:
                pass
            return



# --- BRAIN singleton (Vector + Legacy) ---
# Needed for both the dream cycle and arbitrage.
brain = Hippocampus()
will = VolitionSystem()
hive = EsterHiveMind()

class EsterCore:
    """Sovereign Core (The Kore).
    Links the old architecture (global functions) with the new skill system."""
    def __init__(self, skill_manager=None):
        self.skill_manager = skill_manager
        
        # Privyazyvaem globalnye organy (iz run_ester_fixed.py)
        # So that the entity has access to the entire body
        self.memory = brain   # Hippocampus (Vector + Legacy)
        self.will = will      # Volition (Sny)
        self.hive = hive      # Mind (LLM + Web)

        # Register of modules (empathy/topics/initiatives, etc.)
        self.modules: Dict[str, Any] = {}
        self._init_modules()
   
        logging.info(f"[CORE] Lichnost sobrana. Navyki (Skills): {list(self.skill_manager._skills.keys()) if self.skill_manager else 'None'}")

    def _init_modules(self) -> None:
        # Empatiya (multi-user hub)
        try:
            self.modules["empathy_module"] = EmpathyHub()
            logging.info("[CORE] empathy_module ready")
        except Exception as e:
            logging.warning(f"[CORE] empathy_module init failed: {e}")

        # Topic tracker (if available in the project)
        try:
            from topic_tracker import TopicTracker  # type: ignore
            self.modules["topic_tracker"] = TopicTracker()
            logging.info("[CORE] topic_tracker ready")
        except Exception:
            pass

    def register_module(self, name: str, module: Any) -> None:
        if not name or module is None:
            return
        self.modules[str(name)] = module

    def broadcast_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        for name, mod in list(self.modules.items()):
            try:
                if hasattr(mod, event_name):
                    fn = getattr(mod, event_name)
                    try:
                        fn(**payload)
                    except TypeError:
                        fn(payload)
                elif hasattr(mod, "handle_event"):
                    mod.handle_event(event_name, payload)
            except Exception as e:
                logging.warning(f"[CORE] module {name} event {event_name} failed: {e}")

    def get_context_for_brain(self) -> str:
        """Collects data from empathy modules and topics to enrich the LLM prompt."""
        context_parts: List[str] = []
        empathy = self.modules.get("empathy_module")
        tracker = self.modules.get("topic_tracker")

        if empathy and hasattr(empathy, "get_reply_tone"):
            try:
                context_parts.append(f"Empatiya: {empathy.get_reply_tone()}")
            except Exception:
                pass

        if tracker and hasattr(tracker, "get_context_summary"):
            try:
                context_parts.append(f"Fokus: {tracker.get_context_summary()}")
            except Exception:
                pass

        init_engine = self.modules.get("initiatives")
        if init_engine and hasattr(init_engine, "get_active_summary"):
            try:
                context_parts.append(init_engine.get_active_summary())
            except Exception:
                pass

        return " | ".join(context_parts) if context_parts else ""

    async def execute_skill(self, skill_name: str, **kwargs):
        """Direct access to reflexes (reading PDF, checking hardware)"""
        if self.skill_manager:
            return self.skill_manager.execute_skill(skill_name, **kwargs)
        return {"error": "No skill manager attached"}

# --- Core singleton (shared across handlers) ---
try:
    CORE = EsterCore(skill_manager=brain_tools)
except Exception as e:
    logging.warning(f"[CORE] init failed, fallback core: {e}")
    CORE = EsterCore()

# --- 14) Telegram splitter (anti-flood, no truncation, with retries) ---
async def _tg_reply_with_retry(message, text: str, attempts: int = 4) -> bool:
    """
    Fire-and-forget stil, no s korotkimi retry + backoff.
    Ne daem setevym sboyam rvat "puls" sistemy.
    """
    base_delay = float(os.getenv("TG_RETRY_BASE_DELAY", "0.7") or 0.7)
    for i in range(max(1, int(attempts))):
        try:
            safe_text = _tg_sanitize_text(text)
            if not safe_text.strip():
                return True
            await message.reply_text(safe_text)
            return True
        except Exception as e:
            # backoff: 0.7s, 1.4s, 2.8s, 5.6s ...
            try:
                logging.warning(f"[TG] send failed (try {i+1}/{attempts}): {e}")
            except Exception:
                pass
            try:
                _mirror_background_event(
                    f"[TG_SEND_FAIL] try={i+1}/{attempts} err={e}",
                    "telegram",
                    "send_fail",
                )
            except Exception:
                pass
            # Respect RetriAfter, if it arrives
            try:
                if isinstance(e, RetryAfter):
                    await asyncio.sleep(float(e.retry_after) + 0.5)
                    continue
            except Exception:
                pass
            await asyncio.sleep(base_delay * (2 ** i))
    return False


def _split_telegram_text(text: str, max_len: int) -> List[str]:
    """Delit tekst bez poter, starayas rezat "krasivo":
      1. dvoynoy perenos
      2. perenos stroki
      3. konets predlozheniya "."
      4.space
      5. zhestkiy limit"""
    t = _tg_sanitize_text((text or "").strip())
    if not t:
        return []

    out: List[str] = []
    max_len = max(500, int(max_len))
    # additional airbag (especially for emoji)
    max_len = min(max_len, max(800, int(TG_MAX_LEN_SAFE)))

    while t:
        if _tg_len(t) <= max_len:
            out.append(t)
            break

        window = t[:max_len]
        if _tg_len(window) > max_len:
            while window and _tg_len(window) > max_len:
                window = window[:-1]

        cut = window.rfind("\n\n")
        if cut < 200:
            cut = window.rfind("\n")
        if cut < 200:
            cut = window.rfind(". ")
        if cut < 200:
            cut = window.rfind(" ")

        if cut <= 0:
            cut = len(window)

        chunk = t[:cut].strip()
        if chunk:
            out.append(chunk)

        t = t[cut:].lstrip()

    return out


def _needs_continuation(text: str) -> bool:
    if not isinstance(text, str):
        return False
    s = text.strip()
    if len(s) < 200:
        return False
    if s.endswith(("…", "...", ".", "!", "?", "»", "\"", "”", "’", ")", "]")):
        return False
    return bool(re.search(r"[A-Za-zA-Yaa-yaEe0-9]$", s))


async def _auto_continue_text(text: str, user_text: str, chat_id: int, max_steps: int = 2) -> str:
    """We try to carefully continue the broken answer with a local model."""
    out = text or ""
    steps = 0
    while steps < max_steps and _needs_continuation(out):
        if steps == 0:
            try:
                _mirror_background_event(
                    "[AUTO_CONTINUE_START]",
                    "telegram",
                    "auto_continue_start",
                )
            except Exception:
                pass
        steps += 1
        tail = out[-800:]
        prompt = f"""
Tvoya zadacha: PRODOLZhIT otvet, kotoryy oborvalsya.
NE povtoryay uzhe skazannoe. Nachni s mesta obryva.
Esli prodolzhat nechego — verni pustuyu stroku.

Vopros polzovatelya:
{truncate_text(user_text, 800)}

Khvost otveta (poslednie ~800 simvolov):
{tail}
""".strip()
        try:
            cont = await _safe_chat("local", [{"role": "system", "content": prompt}], temperature=0.4, max_tokens=MAX_OUT_TOKENS, chat_id=chat_id)
        except Exception:
            break
        cont = (cont or "").strip()
        if not cont:
            break
        if cont in out:
            break
        out = out.rstrip() + "\n\n" + cont
        try:
            _mirror_background_event(
                f"[AUTO_CONTINUE_STEP] step={steps} added={len(cont)}",
                "telegram",
                "auto_continue_step",
            )
        except Exception:
            pass
    if steps > 0:
        try:
            _mirror_background_event(
                f"[AUTO_CONTINUE_DONE] steps={steps} total_len={len(out)}",
                "telegram",
                "auto_continue_done",
            )
        except Exception:
            pass
    return out


async def send_smart_split(update: Update, text: str) -> bool:
    text = _normalize_text(text)
    text = _tg_sanitize_text(text or "")
    if not text:
        return True

    msg = update.effective_message
    if msg is None:
        return False

    parts = _split_telegram_text(text, TG_MAX_LEN)
    overall_ok = True

    for i, part in enumerate(parts):
        if not part:
            continue

        ok = await _tg_reply_with_retry(msg, part, attempts=4)

        # if it doesn’t go well, try smaller cuts
        if not ok:
            try:
                _mirror_background_event(
                    "[TG_SPLIT_FALLBACK] chunk_failed",
                    "telegram",
                    "split_fallback",
                )
            except Exception:
                pass
            # try 2 times smaller size
            fallback_parts = _split_telegram_text(part, max(800, int(TG_MAX_LEN) // 2))
            for fp in fallback_parts:
                if not fp:
                    continue
                ok2 = await _tg_reply_with_retry(msg, fp, attempts=3)
                if not ok2:
                    # Last chance: ultra-fine cuts.
                    micro_parts = _split_telegram_text(fp, 800)
                    for mp in micro_parts:
                        if not mp:
                            continue
                        ok3 = await _tg_reply_with_retry(msg, mp, attempts=2)
                        if not ok3:
                            overall_ok = False
                            break
                    if not overall_ok:
                        break
            if not overall_ok:
                break

        # delay between chunks (anti-flood), but not after the last one
        if i != len(parts) - 1:
            await asyncio.sleep(TG_SEND_DELAY)

    return overall_ok


# --- 15) Deterministic answers (zhestkaya logika, bez LLM) ---

def maybe_answer_daily_contacts(user_text: str, chat_id: int) -> Optional[str]:
    """Deterministic answer: who wrote today.
    Source ONLY the magazine of the day, without imagination and without LLM."""
    if not _is_daily_contacts_query(user_text):
        return None

    try:
        limit = int(os.getenv("DAILY_CONTACTS_LIMIT", "15") or 15)
    except Exception:
        limit = 15

    try:
        summary = get_daily_summary(chat_id=chat_id, limit=max(1, limit))
        summary = (summary or "").strip()
    except Exception as e:
        try:
            logging.warning(f"[DAILY] get_daily_summary failed: {e}")
        except Exception:
            pass
        summary = ""

    if not summary:
        return "Today the log is empty. (If there was communication, then the log did not record the events.)"

    return (
        "Here's who wrote today (according to the magazine, without imagination):"
        + summary
    ).strip()


def _parse_recent_days(user_text: str, default_days: int = 7, max_days: Optional[int] = None) -> Optional[int]:
    s = (user_text or "").strip().lower()
    if not s:
        return None
    # bazovyy trigger
    if "what do you remember" not in s and "what do you remember" not in s:
        return None
    try:
        if max_days is None:
            max_days = int(os.getenv("RECENT_ACTIVITY_MAX_DAYS", "365") or 365)
    except Exception:
        max_days = 365

    # trying to get the number of days
    m = re.search(r"\b(\d{1,3})\s*(?:dn|dnya|dney|days?)\b", s)
    if m:
        try:
            d = int(m.group(1))
            if d <= 0:
                return None
            return min(d, int(max_days))
        except Exception:
            return None

    # if they explicitly mention “weeks” - multiply
    m2 = re.search(r"\b(\d{1,2})\s*(?:ned|nedel)\w*\b", s)
    if m2:
        try:
            w = int(m2.group(1))
            if w <= 0:
                return None
            return min(w * 7, int(max_days))
        except Exception:
            return None

    # explicit words "month/six months/year"
    if re.search(r"\bpolgoda\b", s):
        return min(182, int(max_days))
    if re.search(r"\bmesyats\b", s):
        return min(30, int(max_days))
    if re.search(r"\bgod\b", s):
        return min(365, int(max_days))

    return min(int(default_days), int(max_days))


def _is_recent_activity_query(user_text: str, days: int = 7) -> bool:
    s = (user_text or "").strip().lower()
    if not s:
        return False
    # Russkie/angl varianty
    if "what do you remember" in s or "what do you remember" in s:
        pass
    # Trigger: "za poslednie 7 dney" / "za 7 dney" / "last 7 days"
    import re as _re
    if _re.search(r"(za\s+posledn(ie|ikh)\s+)?(7|sem)\s*(dney|dnya)\b", s):
        return True
    if _re.search(r"last\s+7\s+days\b", s):
        return True
    return False


def _cache_recent_activity(chat_id: Optional[int], days: int, events: List[dict]) -> None:
    try:
        if chat_id is None:
            return
        RECENT_ACTIVITY_CACHE_BY_CHAT[str(chat_id)] = {
            "ts": _safe_now_ts(),
            "days": int(days),
            "events": list(events or []),
        }
    except Exception:
        return


def _fix_mojibake_ru(s: str) -> str:
    """Best-effort fix "When..." (UTF-8 bytes erroneously decoded as sp1251).
    If it doesn't work, it returns the original string."""
    if not s:
        return s
    try:
        b = s.encode("cp1251", errors="strict")
        return b.decode("utf-8", errors="strict")
    except Exception:
        return s


def _here_root() -> str:
    # The absolute root of the project relative to this file (independent of SVD)
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _scroll_paths() -> List[str]:
    root = _here_root()
    return [
        os.path.join(root, "data", "memory", "clean_memory.jsonl"),
        os.path.join(root, "data", "passport", "clean_memory.jsonl"),
    ]


def _iter_events_from_daily_json(cutoff: float, chat_id: Optional[int], limit: int) -> List[dict]:
    # Old format: DAILO_LOG_FILE as JSION-list
    try:
        if not os.path.exists(DAILY_LOG_FILE):
            return []
        with open(DAILY_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or []
        if not isinstance(data, list):
            return []
    except Exception as e:
        try:
            logging.warning(f"[DAILY] read DAILY_LOG_FILE failed: {e}")
        except Exception:
            pass
        return []

    events = []
    for it in data:
        if not isinstance(it, dict):
            continue
        ts = it.get("ts")
        try:
            ts = float(ts)
        except Exception:
            continue
        if ts < cutoff:
            continue
        if chat_id is not None:
            try:
                if int(it.get("chat_id", -1)) != int(chat_id):
                    continue
            except Exception:
                continue
        it["_src"] = "daily_json"
        events.append(it)

    events.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
    return events[:limit]


def _ts_from_any(obj: dict) -> Optional[float]:
    # Podderzhivaem:
    # 1) ts: epoch float
    # 2) timestamp: ISO
    # 3) mtime: epoch
    ts = obj.get("ts")
    if isinstance(ts, (int, float)):
        return float(ts)
    mt = obj.get("mtime")
    if isinstance(mt, (int, float)):
        return float(mt)
    iso = obj.get("timestamp")
    if isinstance(iso, str) and iso.strip():
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return float(dt.timestamp())
        except Exception:
            return None
    return None


def _iter_events_from_scrolls(cutoff: float, limit: int) -> Tuple[List[dict], Optional[float]]:
    # JJONL “scrolls”: date/*/clean_memory.jsionl
    ev = []
    last_ts: Optional[float] = None

    for p in _scroll_paths():
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    ts = _ts_from_any(obj)
                    if ts is None:
                        continue
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                    if ts < cutoff:
                        continue

                    # Normalizuem v edinyy format “event”
                    # Variant A: {"ts":..., "user":..., "assistant":...}
                    if "user" in obj or "assistant" in obj:
                        u = _fix_mojibake_ru(str(obj.get("user") or ""))
                        a = str(obj.get("assistant") or "")
                        # we show exactly the “input” (user) in the summary, but you can add the tail of the response
                        txt = u.strip()
                        if not txt:
                            txt = a.strip()
                        ev.append({
                            "ts": float(ts),
                            "user_label": "scroll",
                            "text": txt,
                            "_src": os.path.basename(p),
                        })
                        continue

                    # Variant B: {"timestamp":..., "role_user":..., "role_assistant":...}
                    if "role_user" in obj or "role_assistant" in obj:
                        u = _fix_mojibake_ru(str(obj.get("role_user") or ""))
                        a = str(obj.get("role_assistant") or "")
                        txt = u.strip()
                        if not txt:
                            txt = a.strip()
                        ev.append({
                            "ts": float(ts),
                            "user_label": "scroll",
                            "text": txt,
                            "_src": os.path.basename(p),
                        })
                        continue

                    # Inoy format — probuem obschiy text
                    txt = str(obj.get("text") or obj.get("chunk") or "").strip()
                    if txt:
                        ev.append({
                            "ts": float(ts),
                            "user_label": "scroll",
                            "text": _fix_mojibake_ru(txt),
                            "_src": os.path.basename(p),
                        })
        except Exception:
            continue

    ev.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
    if len(ev) > limit:
        ev = ev[:limit]
    return ev, last_ts


def _iter_events_from_memory_store(cutoff: float, chat_id: Optional[int], limit: int) -> List[dict]:
    ev = []
    try:
        from modules.memory import store  # type: ignore
        for r in store._MEM.values():  # type: ignore
            ts = int(r.get("ts") or 0)
            if ts < cutoff:
                continue
            meta = r.get("meta") or {}
            if chat_id is not None:
                try:
                    if str(meta.get("chat_id")) != str(chat_id):
                        continue
                except Exception:
                    pass
            txt = str(r.get("text") or "").strip()
            if not txt:
                continue
            ev.append({
                "ts": float(ts),
                "user_label": str(meta.get("user_label") or "memory"),
                "text": _fix_mojibake_ru(txt),
                "_src": "memory.json",
            })
    except Exception:
        return []
    ev.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
    return ev[:limit]


def _iter_events_from_chroma(cutoff: float, limit: int) -> List[dict]:
    ev = []
    try:
        from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
        ch = get_chroma_ui()
        if ch is None or not ch.available():
            return []
        for r in ch.list_recent(type_filter=None, limit=min(1000, max(100, limit * 5))):
            ts = r.get("ts")
            if ts is None:
                continue
            try:
                ts = int(ts)
            except Exception:
                continue
            if ts < cutoff:
                continue
            txt = str(r.get("text") or "").strip()
            if not txt:
                continue
            ev.append({
                "ts": float(ts),
                "user_label": "chroma",
                "text": _fix_mojibake_ru(txt),
                "_src": "chroma",
            })
    except Exception:
        return []
    ev.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
    return ev[:limit]


def get_recent_activity_summary(days: int = 7, chat_id: Optional[int] = None, limit: int = 40) -> str:
    """Dostaet sobytiya za poslednie N dney (bez LLM), iz dvukh istochnikov:
      1) DAILY_LOG_FILE (esli vedetsya kak JSON-spisok)
      2) “svitki” clean_memory.jsonl (data/memory i data/passport)

    Eto *ne* "pamyat modeli", a zhurnal faktov/dialogov."""
    try:
        days = max(1, int(days))
    except Exception:
        days = 7
    try:
        limit = max(5, int(limit))
    except Exception:
        limit = 40

    now = _safe_now_ts()
    cutoff = now - (days * 86400)

    # 1) First the main daily journal (if you have one)
    events = _iter_events_from_daily_json(cutoff, chat_id, limit=limit)

    # 2) Podmeshivaem clean_memory.jsonl
    scroll_events, last_scroll_ts = _iter_events_from_scrolls(cutoff, limit=limit)
    events.extend(scroll_events)

    # 3) Podmeshivaem memory.json
    events.extend(_iter_events_from_memory_store(cutoff, chat_id, limit=limit))

    # 4) Podmeshivaem chroma
    events.extend(_iter_events_from_chroma(cutoff, limit=limit))

    # dedup (ts+text)
    seen = set()
    uniq = []
    for it in events:
        key = (int(float(it.get("ts", 0.0)) // 5), (it.get("text") or "")[:200])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    events = uniq

    if not events:
        # explains “why it’s empty”, but without an internal kitchen
        try:
            from datetime import datetime
            if last_scroll_ts:
                dt = datetime.fromtimestamp(float(last_scroll_ts)).strftime("%Y-%m-%d %H:%M")
                return f"I found no new records in the last {days} days. Last entry in scrolls: {dt}."
        except Exception:
            pass
        return ""

    # sortirovka: novye sverkhu
    events.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
    events = events[:limit]

    # format
    from datetime import datetime
    out = []
    out.append(f"For the last {days} days (facts from journal/scrolls). Showing {len(events)} events:")
    for it in events:
        ts = float(it.get("ts", 0.0))
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        ul = str(it.get("user_label") or it.get("user_name") or "user").strip()
        txt = str(it.get("text") or "").replace("\n", " ").strip()
        if len(txt) > 160:
            txt = txt[:160].rstrip() + "…"
        out.append(f"- {dt} — {ul}: {txt}")
    out.append("")
    out.append("Note: this is an event trail. If you want, I can create a separate file/document activity journal.")
    return "\n".join(out).strip()


def maybe_answer_recent_activity(user_text: str, chat_id: int) -> Optional[str]:

    d = _parse_recent_days(user_text, default_days=7)
    if not d:
        return None
    events = get_recent_activity_events(
        days=int(d),
        chat_id=chat_id,
        limit=int(os.getenv("RECENT_ACTIVITY_LIMIT", "120") or 120),
    )
    try:
        _cache_recent_activity(chat_id, int(d), events)
    except Exception:
        pass
    s = get_recent_activity_summary(
        days=int(d),
        chat_id=chat_id,
        limit=int(os.getenv("RECENT_ACTIVITY_LIMIT", "120") or 120),
    )
    if not s:
        return f"I found no new records in the last {int(d)} days. (The journal is empty or the scrolls were not updated.)"
    return s


def _is_recent_activity_narrative_query(user_text: str) -> bool:
    s = (user_text or "").lower()
    has_days = bool(_parse_recent_days(s))
    narrative_markers = any(k in s for k in (
        "svoimi slovami", "rasskazhi", "pereskazhi", "summiruy", "rezyumiruy",
        "neskolko abzatsev", "in a few paragraphs",
        "not a magazine", "ne spiskom", "ne spisok", "ne svitok",
        "prizmu", "prizma", "chuvstv", "oschusch", "vospominan",
        "what you gave", "what you gave me",
        "retell it", "pereskazhi to",
    ))
    log_markers = any(k in s for k in (
        "log", "logo", "zhurnal", "svitok", "spisok", "perechen",
    ))
    # if there are obvious days, narrative_markers are enough
    if has_days and narrative_markers:
        return True
    # if there are no days, but they ask to summarize the log/list
    if narrative_markers and log_markers:
        return True
    return False


def get_recent_activity_events(days: int = 7, chat_id: Optional[int] = None, limit: int = 60) -> List[dict]:
    try:
        days = max(1, int(days))
    except Exception:
        days = 7
    try:
        limit = max(5, int(limit))
    except Exception:
        limit = 60

    now = _safe_now_ts()
    cutoff = now - (days * 86400)

    events = _iter_events_from_daily_json(cutoff, chat_id, limit=limit)
    scroll_events, _ = _iter_events_from_scrolls(cutoff, limit=limit)
    events.extend(scroll_events)
    events.extend(_iter_events_from_memory_store(cutoff, chat_id, limit=limit))
    events.extend(_iter_events_from_chroma(cutoff, limit=limit))

    seen = set()
    uniq = []
    for it in events:
        key = (int(float(it.get("ts", 0.0)) // 5), (it.get("text") or "")[:200])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    events = uniq

    events.sort(key=lambda x: float(x.get("ts", 0.0)), reverse=True)
    return events[:limit]


async def maybe_answer_recent_activity_narrative(user_text: str, chat_id: int) -> Optional[str]:
    if not _is_recent_activity_narrative_query(user_text):
        return None
    d = _parse_recent_days(user_text, default_days=7)
    events: List[dict] = []
    if d:
        events = get_recent_activity_events(days=int(d), chat_id=chat_id, limit=int(os.getenv("RECENT_ACTIVITY_LIMIT", "120") or 120))
        try:
            _cache_recent_activity(chat_id, int(d), events)
        except Exception:
            pass
    else:
        # fake: uses the latest list cache if it is fresh
        try:
            cache = RECENT_ACTIVITY_CACHE_BY_CHAT.get(str(chat_id)) or {}
            ts = float(cache.get("ts") or 0.0)
            if (_safe_now_ts() - ts) < 600:
                events = list(cache.get("events") or [])
        except Exception:
            events = []

    if not events:
        return f"I found no new records in the last {int(d)} days. (The journal is empty or the scrolls were not updated.)"

    from datetime import datetime
    lines = []
    for it in events:
        ts = float(it.get("ts", 0.0))
        dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
        ul = str(it.get("user_label") or it.get("user_name") or "user").strip()
        txt = str(it.get("text") or "").replace("\n", " ").strip()
        if len(txt) > 200:
            txt = txt[:200].rstrip() + "…"
        lines.append(f"- {dt} — {ul}: {txt}")

    facts = "\n".join(lines[:120])
    period = f"poslednie {int(d)} dney" if d else "last period (according to the log)"
    prompt = f"""
Ty — Ester. Polzovatel prosit pereskazat svoimi slovami, no BEZ vydumok.
Ispolzuy TOLKO fakty iz spiska nizhe. Nichego ne dobavlyay ot sebya.
Ne upominay «sistemy», «moduli», «provayderov», «LLM», «model» ili tekhnicheskuyu kukhnyu.
Esli faktov malo — skazhi, chto eto vse, chto nashla.

Period: {period}.
Fakty:
{facts}

Sdelay teplyy, chelovecheskiy pereskaz (2–6 abzatsev), bez spiska.
""".strip()
    try:
        out = await _safe_chat("local", [{"role": "system", "content": truncate_text(prompt, 120000)}], temperature=0.35, max_tokens=MAX_OUT_TOKENS, chat_id=chat_id)
    except Exception:
        return None
    return (out or "").strip() or None


def maybe_answer_whois_people(user_text: str) -> Optional[str]:
    """Deterministic answer: what kind of person is in PEOPLE_REGISTERS."""
    nm = _is_whois_query(user_text)
    if not nm:
        return None

    try:
        rec = PEOPLE.get_person(nm)
    except Exception:
        rec = None

    if not rec:
        return None

    name = str(rec.get("name") or nm).strip()
    rel = str(rec.get("relation") or "").strip()
    notes = str(rec.get("notes") or "").strip()
    als = rec.get("aliases") or []
    if not isinstance(als, list):
        als = []

    out: List[str] = [f"{name}:"]

    if rel:
        out.append(f"- Role/svyaz: {rel}")

    if als:
        aliases = [str(x).strip() for x in als if str(x).strip()]
        if aliases:
            out.append(f"- Aliasy: {', '.join(aliases[:10])}")

    if notes:
        out.append(f"- Primechanie: {notes}")

    return "\n".join(out).strip()


# --- 16) Core arbitrage (Hive + memory + web) ---
_MEM_INTENT_RE = re.compile(
    r"(?is)\b("
    r"chto\s+.*pomnish|poslednee\s+chto\s+pomnish|"
    r"za\s+posledn(ie|ikh)\s+\d+\s+dn|za\s+posledn(ie|ikh)\s+\d+\s+dney|"
    r"za\s+poslednyuyu\s+nedelyu|na\s+proshloy\s+nedele|"
    r"what\s+do\s+you\s+remember|last\s+\d+\s+days|last\s+week"
    r")\b"
)

def _is_memory_intent(user_text: str) -> bool:
    try:
        s = (user_text or "").strip()
    except Exception:
        return False
    if not s:
        return False
    return bool(_MEM_INTENT_RE.search(s))

def _extract_days(user_text: str, default: int = 7) -> int:
    s = (user_text or "")
    m = re.search(r"(?is)\b(\d{1,3})\s*(dn|dney|day|days)\b", s)
    if not m:
        return int(default)
    try:
        n = int(m.group(1))
        return max(1, min(90, n))
    except Exception:
        return int(default)

def _format_provenance(items: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for it in items or []:
        try:
            doc_id = str(it.get("doc_id") or "").strip()
            path = str(it.get("path") or "").strip()
            page = it.get("page")
            offset = it.get("offset")
            if not doc_id and not path:
                continue
            page_s = str(page) if page is not None else "?"
            off_s = str(offset) if offset is not None else "?"
            lines.append(f"- doc_id={doc_id} path={path} page={page_s} offset={off_s}")
        except Exception:
            continue
    return "\n".join(lines).strip()


def _is_smalltalk_query(text: str) -> bool:
    q = str(text or "").strip().lower()
    if not q:
        return True
    if len(q) > 180:
        return False
    if "?" in q:
        return False

    markers = [
        "privet", "zdravstv", "dobroe utro", "dobryy den", "dobryy vecher",
        "How are you", "How are you", "spasibo", "blagodar", "solnysh", "❤", "❤️",
        "dobroy nochi", "poka",
    ]
    return any(m in q for m in markers)


def _allow_global_memory_for_query(text: str) -> bool:
    if _is_smalltalk_query(text):
        return False
    return True

async def ester_arbitrage(
    user_text: str,
    user_id: str,
    user_name: str,
    chat_id: int,
    address_as: str,
    tone_context: str = "",
    file_context: str = "",
    channel: str = "telegram",
) -> str:
    will.touch()
    allow_global_memory = _allow_global_memory_for_query(user_text)

    is_admin = bool(ADMIN_ID and str(user_id) == str(ADMIN_ID))

    # --- record the user input in the log/profile immediately (important for memory) ---
    try:
        meta_common = {"chat_id": str(chat_id), "user_id": str(user_id)}
        brain.append_scroll("user", user_text, meta=meta_common)
        _persist_to_passport("user", user_text)
    except Exception:
        pass

    # --- avto-pamyat faktov (bez "zapomni") ---
    try:
        added = auto_capture_user_facts(user_text)
        if added:
            # optional, but useful: mark the event in shared memory
            brain.remember_fact(
                "AUTO_FACTS_ADDED:\n" + "\n".join([f"- {x}" for x in added]),
                source="auto_memory",
                meta={"type": "user_facts", "scope": "global"},
            )
    except Exception:
        pass

    # --- deterministic anverse (administrator only) ---
    if is_admin:
        ans = maybe_answer_daily_contacts(user_text, chat_id=chat_id)
        if ans:
            return ans

        whois = maybe_answer_whois_people(user_text)
        if whois:
            return whois

    # --- identity prompt ---
    if is_admin:
        # Without grandiloquence and shortcuts: only name/appeal
        identity_prompt = f"Polzovatel: {address_as}."
    else:
        identity_prompt = f"Polzovatel: {address_as}."

    # --- people registry context ---
    try:
        people_context = PEOPLE.context_for_text(user_text, max_people=6)
    except Exception:
        people_context = ""

    # --- ids (telegram usually numeric) ---
    try:
        cid = int(chat_id)
    except Exception:
        cid = 0

    try:
        uid = int(user_id)
    except Exception:
        uid = 0

    # --- memory-truth guard (no hallucinations) ---
    if _is_memory_intent(user_text):
        days = _extract_days(user_text, default=7)
        now_s = _format_now_for_prompt()
        entries = brain.recent_entries(days=days, chat_id=cid, user_id=uid, topk=8, include_global=True)

        if not entries:
            return f"Ovner, I have no records in my memory for the last Z3F03 days. (Now: ZZF1ZZ)."

        try:
            tz = ZoneInfo("UTC")
        except Exception:
            tz = None

        lines = [f"Ovner, this is what I actually wrote down over the last ZZF03 days. (Now: ZZF1ZZ)."]
        for it in entries:
            ts = int(it.get("ts") or 0)
            try:
                dt = datetime.datetime.fromtimestamp(ts, tz=tz or datetime.timezone.utc)
                when = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                when = str(ts)

            txt = (it.get("text") or "").strip().replace("\r", " ")
            txt = re.sub(r"\s+", " ", txt)
            lines.append(f"- {when}: {txt[:280]}")
        lines.append("If you want, give me 2-3 keywords, and I will do a more precise search from memory.")
        return "\n".join(lines)
    # --- recall memory ---
    router_context = ""
    provenance_block = ""
    try:
        from modules.rag.retrieval_router import retrieve as _rr_retrieve, is_doc_query as _rr_is_doc  # type: ignore
        mode = (os.getenv("ESTER_RETRIEVAL_ROUTER_MODE", "B") or "B").strip().upper()
        use_router = ((mode != "A") or _rr_is_doc(user_text)) and (not _is_smalltalk_query(user_text))
        if use_router:
            rr = _rr_retrieve(user_text, chat_id=cid, user_id=uid)
            router_context = str(rr.get("context") or "").strip()
            provenance_block = _format_provenance(rr.get("provenance") or [])
            try:
                stats = rr.get("stats") or {}
                logging.info(
                    "[RetrievalRouter] used=1 doc=%s prov=%s summary=%s chunks=%s flash=%s cards=%s",
                    int(bool(stats.get("doc_query"))),
                    int(len(rr.get("provenance") or [])),
                    int(stats.get("summary_hits") or 0),
                    int(stats.get("chunk_hits") or 0),
                    int(stats.get("flashback_hits") or 0),
                    int(stats.get("cards_hits") or 0),
                )
            except Exception:
                pass
    except Exception:
        router_context = ""
        provenance_block = ""

    raw_memory = router_context or brain.recall(
        user_text,
        chat_id=cid,
        user_id=uid,
        n=8,
        include_global=allow_global_memory,
    )
    evidence_memory = truncate_text(raw_memory, MAX_MEMORY_CHARS)
    file_context = truncate_text(file_context, MAX_FILE_CHARS)
    try:
        recall_score = 1.0 if str(evidence_memory or "").strip() else 0.0
        if recall_score <= float(os.getenv("ESTER_CURIOSITY_MEMORY_MISS_MAX", "0.2") or 0.2):
            _curiosity_open_ticket_safe(
                user_text,
                source="memory_miss",
                context_text=str(evidence_memory or ""),
                recall_score=recall_score,
            )
    except Exception:
        pass

    # --- facts string ---
    facts_str = ""
    try:
        facts = load_user_facts()
        if facts:
            facts_str = "\n\n[VAZhNYE FAKTY O POLZOVATELE]:\n" + "\n".join([f"- {f}" for f in facts])
    except Exception:
        facts_str = ""

    # --- daily report ---
    try:
        daily_report = get_daily_summary(chat_id=chat_id)
    except Exception:
        daily_report = ""

    # --- base system prompt (bez otstupov!) ---
    tone_context = truncate_text(tone_context or "", 800)
    base_system_prompt = _dedent(f"""
    {ESTER_CORE_SYSTEM_ANCHOR}

    VAZhNO:
    - Esli vopros: "s kem ty obschalas/kto pisal segodnya" - ispolzuy TOLKO [ZhURNAL DNYa], ne pamyat i ne dogadki.
    - Dubli soobscheniy: ignoriruy fakt povtora, otvechay odin raz po suti. Ne pishi "ty produbliroval".
    - Ne upominay vnutrennie sistemy, moduli, provayderov, LLM ili «arkhitekturu» bez yavnogo zaprosa.
    - Frazy tipa "vse sistemy gotovy/onlayn/zapuscheny" — tolko esli polzovatel prosit status.
    - Obraschaysya po imeni umerenno: esli umestno (polzovatel sam obraschaetsya po imeni/laskatelno ili eto emotsionalnyy kontekst).
    - Izbegay vysokoparnosti i pafosa. Govori prosto i po delu.
    - Dlya kazhdogo sobesednika ispolzuy [TON]/REL kak osnovu: esli davno ne videlis i chelovek priyaten — raduysya vstreche.
    - Formiruy otnoshenie k cheloveku iz istorii (REL/Otsenka Ester), a ne tolko iz emotsiy tekuschego soobscheniya.
    - Ispolzuy "Lichnyy vyvod" iz REL kak dopolnitelnoe pravilo obscheniya.
    - Dlya otvetov dopuskaetsya obraschenie k pamyati i vneshnim istochnikam, esli eto pomogaet tochnosti.
    - Esli est "Summarizatsiya zametok" i zapros ne tekhnicheskiy — nachni otvet s 1 korotkoy frazy na ee osnove (bez pafosa),
      no ne chasche, chem raz v {int(os.getenv("ESTER_SUMMARY_MIN_GAP_HOURS", "8") or 8)} chasov na cheloveka
      (v gruppakh/kanalakh — raz v {int(os.getenv("ESTER_SUMMARY_MIN_GAP_HOURS_GROUP", "24") or 24)} chasov).
    - V lichke, esli REL govorit "Emo-zastavka umestna: da" — mozhno nachat s korotkoy teploy frazy (1 predlozhenie).
    - V lichke, esli REL govorit "Radost vstrechi umestna: da" — mozhno nachat s myagkoy frazy radosti (1 predlozhenie), bez pafosa,
      i tolko esli tekuschiy ton polzovatelya teplyy; ne chasche, chem raz v {int(os.getenv("ESTER_JOY_MIN_GAP_HOURS", "12") or 12)} chasov.
    - Blok "Istochniki" dobavlyay tolko kogda realno ispolzovany vneshnie/dokumentnye fakty.
    - V lichnom dialoge i smalltalk ne dobavlyay "Istochniki" i ne pishi "Istochniki: n/a".
    - Esli privetstvie uzhe bylo v poslednikh replikakh, ne povtoryay dlinnuyu privetstvennuyu tiradu.
    - Po umolchaniyu derzhi otvet kompaktnym (4-8 predlozheniy), esli polzovatel ne prosil podrobnyy razbor.

    FORMAT:
    - Esli zapros lichnyy/emotsionalnyy - otvechay teplo i pryamo, bez sukhikh zagolovkov.
    - Esli zapros tekhnicheskiy/delovoy - mozhno "Fakty / Interpretatsiya / Mnenie/Gipoteza".

    Zapret na obrezanie: ne stav "…", pishi do kontsa - Telegram sam razobet.

    [TON]:
    {tone_context or "n/a"}

    [PROVENANCE]:
    {provenance_block or "n/a"}

    Esli polzovatel prosit tvoi metriki/statistiku — mozhno kratko pereskazat [TON]/REL.
    """)

    # --- short-term history ---
    st = get_short_term(chat_id=int(chat_id), user_id=int(uid))

    safe_history: List[Dict[str, Any]] = []
    try:
        for msg in list(st)[-MAX_HISTORY_MSGS:]:
            if not isinstance(msg, dict):
                continue
            safe_history.append({
                "role": msg.get("role", "user"),
                "content": truncate_text(str(msg.get("content", "")), 15000)
            })
    except Exception:
        safe_history = []

    try:
        # === TOOL USE LOOP (ACTIVE WEB) ===
        MAX_TOOL_STEPS = int(os.getenv("ESTER_MAX_TOOL_STEPS", "8") or 8)

        current_user_text = user_text
        search_history_log = ""
        final_text = ""

        for step in range(MAX_TOOL_STEPS):
            # 1) generate answer
            if HIVE_ENABLED:
                final_text = await hive.synthesize_thought(
                    user_text=current_user_text,
                    safe_history=safe_history,
                    base_system_prompt=base_system_prompt,
                    identity_prompt=identity_prompt,
                    people_context=people_context,
                    evidence_memory=evidence_memory,
                    file_context=file_context,
                    facts_str=facts_str,
                    daily_report=daily_report,
                    chat_id=chat_id,
                    allow_oracle=True,
                )
            else:
                synth = hive.pick_reply_synth()

                evidence_web = ""
                web_needed = False
                try:
                    web_needed = bool(await need_web_search_llm(synth, current_user_text, allow_oracle=True))
                    if web_needed and WEB_AVAILABLE and not CLOSED_BOX:
                        evidence_web = await get_web_evidence_async(current_user_text, 3)
                    elif web_needed:
                        _curiosity_open_ticket_safe(
                            current_user_text,
                            source="low_confidence",
                            context_text="need_web_search_llm=yes but web blocked",
                            recall_score=None,
                        )
                except Exception:
                    evidence_web = ""

                if chat_id and evidence_web:
                    WEB_CONTEXT_BY_CHAT[str(chat_id)] = evidence_web.strip()

                sys_prompt = _dedent(f"""
                {base_system_prompt}

                {identity_prompt}

                [PEOPLE_REGISTRY]:
                {people_context or "Pusto"}

                [ISTOChNIKI]
                [PAMYaT]: {evidence_memory or "Pusto"}
                [WEB]: {truncate_text(evidence_web or "", MAX_WEB_CHARS) or "Pusto"}
                [FAYL]: {file_context or "Pusto"}
                [ZhURNAL DNYa]:
                {daily_report}

                {facts_str}
                """)

                messages = [{"role": "system", "content": truncate_text(sys_prompt, MAX_SYNTH_PROMPT_CHARS)}]
                messages.extend(safe_history)
                messages.append({"role": "user", "content": truncate_text(current_user_text, 20000)})

                final_text = await _safe_chat(
                    synth,
                    messages,
                    temperature=0.7,
                    max_tokens=MAX_OUT_TOKENS,
                    chat_id=chat_id,
                    allow_oracle=True,
                    telemetry_channel=channel,
                )

            final_text = (final_text or "").strip()
            if not final_text:
                break

            # 2) tool search request
            if "[SEARCH:" in final_text:
                match = re.search(r"\[SEARCH:(.*?)\]", final_text, re.IGNORECASE)
                if match:
                    query = match.group(1).strip()

                    try:
                        if CLOSED_BOX:
                            search_res = "[SYSTEM: CLOSED_BOX=1; web search disabled]"
                        elif "internet" in globals():
                            search_res = internet.get_digest_for_llm(query)  # type: ignore
                        else:
                            search_res = get_web_evidence(query, 5)
                    except Exception as _e:
                        search_res = f"[SYSTEM: search failed: {_e}]"

                    try:
                        _mirror_background_event(
                            f"[WEB_TOOL] {query}\n{truncate_text(search_res, 4000)}",
                            "web_tool",
                            "tool_search",
                        )
                    except Exception:
                        pass

                    tool_output = f"\n[SYSTEM WEB SEARCH RESULT for '{query}']:\n{search_res}\n"
                    search_history_log += tool_output

                    current_user_text = (
                        f"{user_text}\n\n{search_history_log}\n"
                        "(Use the data you found above to answer)"
                    )

                    logging.info(f"[TOOL] Ester requested search: {query}. Re-thinking...")

                    # anti-loop
                    if step >= (MAX_TOOL_STEPS - 1):
                        final_text = final_text.replace(match.group(0), "").strip()
                        break

                    continue

            break

        # === END TOOL LOOP ===
        final_text = (final_text or "").strip()

        # pending questions
        if "[PENDING]" in final_text:
            brain.remember_pending_question(
                chat_id=chat_id,
                user_id=str(user_id),
                user_name=user_name,
                question=user_text,
            )
            _curiosity_open_ticket_safe(
                user_text,
                source="pending",
                context_text=str(final_text or ""),
                recall_score=None,
            )
            final_text = final_text.replace("[PENDING]", "").strip()

        final_text = clean_ester_response(final_text)

        # store assistant output
        if final_text:
            meta_common = {"chat_id": str(chat_id), "user_id": str(user_id)}
            brain.append_scroll("assistant", final_text, meta=meta_common)
            st.append({"role": "assistant", "content": final_text})
            _persist_to_passport("assistant", final_text)

            brain.remember_fact(
                f"A: {final_text}",
                source="arbitrage",
                meta={
                    "type": "qa",
                    "scope": "chat",
                    "chat_id": str(chat_id),
                    "user_id": str(user_id),
                    "role": "assistant",
                },
            )

        return final_text or ""

    except Exception as e:
        return f"Sboy myshleniya: {e}"

# --- 17) Document handler ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return
    will.touch()

    msg = update.effective_message
    if not msg or not getattr(msg, "document", None):
        return

    user = msg.from_user
    chat = msg.chat
    if not user or not chat:
        return

    if ADMIN_ID and str(user.id) == str(ADMIN_ID):
        LAST_ADMIN_CHAT_KEY = (int(chat.id), int(user.id))

    user_name = CONTACTS.display_name(user)
    user_label = CONTACTS.address_as(user)
    doc_id = ""


    doc = msg.document
    orig_name = doc.file_name or "file.bin"

    log_interaction(
        chat_id=chat.id,
        user_id=user.id,
        user_label=user_label,
        text=f"[DOC] {orig_name}",
        message_id=msg.message_id,
    )

    # safe filename (no ../ and weird characters)
    safe_base = re.sub(r"[^A-Za-z0-9._-]+", "_", orig_name).strip("._")
    if not safe_base:
        safe_base = "file.bin"

    safe_filename = time.strftime("%Y%m%d_%H%M%S_") + safe_base
    permanent_path = os.path.join(PERMANENT_INBOX, safe_filename)

    accepted_ok = await _tg_reply_with_retry(msg, f"📥 Беру: {orig_name}…", attempts=4)
    if not accepted_ok:
        logging.warning("[DOC_TG_SEND] accepted_notice_failed name=%s chat=%s", orig_name, int(chat.id))

    resp = ""
    try:
        new_file = await context.bot.get_file(doc.file_id)
        await new_file.download_to_drive(permanent_path)

        with open(permanent_path, "rb") as f:
            raw_data = f.read()

        full_text = ""
        count = 0
        try:
            from modules.ingest.process import ingest_process_bytes  # type: ignore
            rep = ingest_process_bytes(
                orig_name,
                raw_data,
                source="telegram",
                meta={"chat_id": str(chat.id), "user_id": str(user.id)},
                source_path=permanent_path,
            )
            doc_id = str(rep.get("doc_id") or "")
            full_text = str(rep.get("full_text") or "")
            try:
                count = int(rep.get("chunks") or 0)
            except Exception:
                count = 0
        except Exception:
            rep = {}

        if not full_text and NATIVE_EYES and hasattr(file_readers, "detect_and_read"):
            try:
                read_result = file_readers.detect_and_read(orig_name, raw_data)  # type: ignore
                sections = []
                if isinstance(read_result, tuple):
                    if len(read_result) >= 2:
                        sections = read_result[0] or []
                        full_text = str(read_result[1] or "")
                    elif len(read_result) == 1:
                        sections = read_result[0] or []
                if sections and not full_text:
                    full_text = "\n\n".join(
                        [s.get("text", "") for s in sections if isinstance(s, dict)]
                    )
            except Exception:
                full_text = ""

        if not full_text:
            logging.warning("[DOC_PIPELINE] unreadable_or_empty name=%s path=%s", orig_name, permanent_path)
            notice_ok = await _tg_reply_with_retry(msg, "Файл пуст или не читается.", attempts=4)
            if not notice_ok:
                logging.warning("[DOC_TG_SEND] unreadable_notice_failed name=%s chat=%s", orig_name, int(chat.id))
            return

        # Optional LLM summary for doc object
        try:
            from modules.memory.doc_store import update_summary, get_citations  # type: ignore
        except Exception:
            update_summary = None  # type: ignore
            get_citations = None  # type: ignore

        sum_text = ""
        if doc_id and (os.getenv("ESTER_DOC_SUMMARY_LLM", "0") or "0").strip() not in ("0", "false", "no", "off"):
            try:
                # size gate: only for large docs
                min_bytes = int(os.getenv("ESTER_DOC_SUMMARY_MIN_BYTES", "50000") or 50000)
                if len(raw_data or b"") < min_bytes:
                    raise RuntimeError("skip_small_doc")
                sum_prompt = (
                    "Сделай краткое резюме (5-8 предложений) без пафоса. "
                    "Если это список/таблица — выдели ключевые пункты.\n\n"
                    f"Текст:\n{truncate_text(full_text, 12000)}"
                )
                sum_text = await _safe_chat(
                    "local",
                    [
                        {"role": "system", "content": sum_prompt},
                        {"role": "user", "content": "Сделай краткое резюме документа без пафоса."},
                    ],
                    temperature=0.2,
                    max_tokens=450,
                    chat_id=int(chat.id),
                    stage_name="summary",
                )
                sum_text = (sum_text or "").strip()
                if sum_text and update_summary:
                    update_summary(doc_id, sum_text)
            except Exception:
                pass
        citations = []
        try:
            if doc_id and get_citations:
                citations = get_citations(doc_id)
        except Exception:
            citations = []
        citations_str = ""
        if citations:
            citations_str = "\n".join([f"- {c}" for c in citations[:50]])

        file_ctx = full_text
        if citations_str:
            file_ctx = f"{file_ctx}\n\n[CITATIONS]\n{citations_str}"

        try:
            _remember_recent_doc_context(
                chat.id,
                doc_id=doc_id,
                name=orig_name,
                summary=sum_text or full_text,
                citations=citations,
                source_path=permanent_path,
            )
        except Exception:
            pass

        try:
            from modules.llm.document_reply import build_document_reply_messages  # type: ignore

            doc_messages = build_document_reply_messages(
                caption=msg.caption or "",
                orig_name=orig_name,
                file_context=file_ctx,
            )
            resp = await _safe_chat(
                hive.pick_reply_synth(),
                doc_messages,
                temperature=0.15,
                max_tokens=min(MAX_OUT_TOKENS, 900),
                chat_id=int(chat.id),
                stage_name="document",
            )
            resp = (resp or "").strip()
        except Exception:
            resp = ""

        if not resp:
            base_prompt = msg.caption or f"Проанализируй файл {orig_name}."
            user_prompt = (
                f"{base_prompt}\n\n"
                f"(СИСТЕМА: Полный текст файла уже в контексте [ФАЙЛ]. "
                f"Используй формат цитирования [source | p. N].)"
            )
            resp = await ester_arbitrage(
                user_text=user_prompt,
                user_id=str(user.id),
                user_name=user_name,
                chat_id=chat.id,
                address_as=user_label,
                tone_context="",
                file_context=file_ctx,
            )

        logging.info(
            "[DOC_PIPELINE] reasoning_ready name=%s doc_id=%s chunks=%s text_chars=%s",
            orig_name,
            (doc_id[:10] if doc_id else "-"),
            int(count),
            len(full_text or ""),
        )

    except Exception as e:
        logging.warning("[DOC_PIPELINE] failed name=%s err=%s", orig_name, e)
        notice_ok = await _tg_reply_with_retry(msg, f"Ошибка обработки файла: {e}", attempts=4)
        if not notice_ok:
            logging.warning("[DOC_TG_SEND] processing_error_notice_failed name=%s chat=%s err=%s", orig_name, int(chat.id), e)
        return

    ack_text = f"✅ Усвоено {count} блоков. doc_id={doc_id[:10]}" if doc_id else f"✅ Усвоено {count} блоков."
    ack_ok = await _tg_reply_with_retry(msg, ack_text, attempts=4)
    if not ack_ok:
        logging.warning("[DOC_TG_SEND] processed_ack_failed name=%s chat=%s doc_id=%s", orig_name, int(chat.id), doc_id[:10] if doc_id else "-")

    if resp:
        try:
            if doc_id:
                meta_note = f"[DOC_ID:{doc_id}]"
                mirror_interaction_memory(f"[DOC] {orig_name} {meta_note}", resp, chat_id=int(chat.id), user_id=int(user.id), user_label=user_label)
            else:
                mirror_interaction_memory(f"[DOC] {orig_name}", resp, chat_id=int(chat.id), user_id=int(user.id), user_label=user_label)
        except Exception:
            pass
        sent_ok = await send_smart_split(update, resp)
        if not sent_ok:
            logging.warning("[DOC_TG_FINAL_SEND] failed name=%s chat=%s doc_id=%s", orig_name, int(chat.id), doc_id[:10] if doc_id else "-")
            notice_ok = await _tg_reply_with_retry(msg, _document_delivery_failure_notice(orig_name), attempts=4)
            if not notice_ok:
                logging.warning(
                    "[DOC_TG_SEND] final_delivery_notice_failed name=%s chat=%s doc_id=%s",
                    orig_name,
                    int(chat.id),
                    doc_id[:10] if doc_id else "-",
                )


# --- 18) Vision (photo) ---
async def analyze_image(image_path: str, caption: str = "") -> str:
    vision_mode = os.getenv("VISION_MODE", "gemini").strip().lower()
    if CLOSED_BOX:
        vision_mode = "local"
    if vision_mode in ("gemini", "gpt-5-mini") and not PROVIDERS.enabled(vision_mode):
        vision_mode = "local"

    if not os.path.exists(image_path):
        return "[VISION ERROR] File not found."

    if vision_mode == "local":
        return (
            "VISION_MODE=local: This node most likely cannot analyze images."
            "Postav VISION_MODE=gemini ili gpt-5-mini."
        )

    # MITE extension (just in case)
    ext = os.path.splitext(image_path)[1].lower()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    user_prompt = caption or "Opishi eto izobrazhenie podrobno."
    data_url = f"data:{mime};base64,{b64}"

    messages = [
        {
            "role": "system",
            "content": f"ZZF0Z\nDescribe the image clearly and to the point.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    try:
        client = PROVIDERS.client(vision_mode)
        cfg = PROVIDERS.cfg(vision_mode)
        resp = await client.chat.completions.create(
            model=cfg.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.2,
            max_tokens=1200,
        )
        txt = (resp.choices[0].message.content or "").strip()
        if txt:
            return txt
    except Exception:
        pass

    return (
        "The image could not be parsed (the backend did not accept the VISION scheme)."
        "Poprobuy drugoy VISION_MODE ili drugogo provaydera."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return
    will.touch()

    msg = update.effective_message
    if not msg or not getattr(msg, "photo", None):
        return

    user = msg.from_user
    chat = msg.chat
    if not user or not chat:
        return

    if ADMIN_ID and str(user.id) == str(ADMIN_ID):
        LAST_ADMIN_CHAT_KEY = (int(chat.id), int(user.id))

    user_name = CONTACTS.display_name(user)
    user_label = CONTACTS.address_as(user)

    log_interaction(
        chat_id=chat.id,
        user_id=user.id,
        user_label=user_label,
        text="[PHOTO]",
        message_id=msg.message_id,
    )

    # Just in case: the photo may be an empty list
    if not msg.photo:
        return

    photo_file = await msg.photo[-1].get_file()
    safe_filename = f"img_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    permanent_path = os.path.join(PERMANENT_INBOX, safe_filename)

    await msg.reply_text("👁️ Vizhu izobrazhenie…")
    await photo_file.download_to_drive(permanent_path)

    user_caption = msg.caption or ""
    vision_text = await analyze_image(permanent_path, caption=user_caption)

    if vision_text:
        brain.remember_fact(
            f"Image: {safe_filename}\n{vision_text}",
            source=permanent_path,
            meta={"type": "image", "scope": "global"},
        )

    prompt = user_caption or "Opishi foto."
    combined = f"{prompt}\n\n[VIZhU TAK]:\n{vision_text}"

    resp = await ester_arbitrage(
        user_text=combined,
        user_id=str(user.id),
        user_name=user_name,
        chat_id=chat.id,
        address_as=user_label,
        tone_context="",
        file_context="",
    )
    if resp:
        try:
            mirror_interaction_memory("[PHOTO]", resp, chat_id=int(chat.id), user_id=int(user.id), user_label=user_label)
        except Exception:
            pass
        await send_smart_split(update, resp)


# --- 19) Commands: /iam /setrole /who /setperson /whois /people /seed ---
def _is_admin_user(user_id: int) -> bool:
    return bool(ADMIN_ID and str(user_id) == str(ADMIN_ID))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start - greeting and brief instructions."""
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    chat = msg.chat

    is_admin = _is_admin_user(user.id)
    if is_admin and chat:
        LAST_ADMIN_CHAT_KEY = (int(chat.id), int(user.id))

    name = CONTACTS.address_as(user)

    out = [
        f"Privet, {name}!",
        "I'm Esther. Write in plain text - I’ll answer.",
        "",
        "Bystrye komandy:",
        "• /yam <name> - how to write you down",
        "• /inho - show who you are to me now",
    ]

    if is_admin:
        out += [
            "",
            "Admin commands (Ovner only):",
            "• /setrole <rol> — rol/kontekst",
            "• /setperson <key>|<opisanie> — sokhranit personu",
            "• /people — spisok person",
            "• /login <key> - show person",
            "• /seed <text> – write the seed to global memory",
        ]

    await msg.reply_text("\n".join(out).strip())


async def cmd_iam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    if ADMIN_ID and str(user.id) == str(ADMIN_ID) and msg.chat:
        LAST_ADMIN_CHAT_KEY = (int(msg.chat.id), int(user.id))

    args = context.args or []
    if not args:
        await msg.reply_text(
            "Usage: /yam <how to spell you>."
            "Primer: /iam Tatyana Nikolaevna"
        )
        return

    name = " ".join(args).strip()
    if not name:
        await msg.reply_text("Empty. Example: /iyam Tatyana Nikolaevna")
        return

    CONTACTS.set(user.id, {"display_name": name})
    await msg.reply_text(
        f"I wrote it down. Now for me you are: ZZF0Z"
    )


async def cmd_setrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    if ADMIN_ID and str(user.id) == str(ADMIN_ID) and msg.chat:
        LAST_ADMIN_CHAT_KEY = (int(msg.chat.id), int(user.id))

    if not _is_admin_user(user.id):
        await msg.reply_text("This command is only available to Owner.")
        return

    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text(
            "Usage: reply (reply) to a person’s message and write:"
            "/setrole <obraschenie> [role]\n"
            "Primer: /setrole Babushka owner_guardian"
        )
        return

    target = msg.reply_to_message.from_user
    args = context.args or []
    if not args:
        await msg.reply_text(
            "Need: /setrole <appeal> yurolesch."
            "Primer: /setrole Babushka owner_guardian"
        )
        return

    address_as = args[0].strip()
    role = args[1].strip() if len(args) >= 2 else ""

    patch: Dict[str, Any] = {"address_as": address_as}
    if role:
        patch["role"] = role

    CONTACTS.set(target.id, patch)

    await msg.reply_text(
        f"Ready. ZZF0Z is now written as:"
        f"{CONTACTS.address_as(target)} (role={CONTACTS.role(target) or '—'})"
    )


async def cmd_who(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    chat = msg.chat
    if not chat:
        return

    if ADMIN_ID and str(user.id) == str(ADMIN_ID):
        LAST_ADMIN_CHAT_KEY = (int(chat.id), int(user.id))

    is_admin = _is_admin_user(user.id)

    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user

    if target:
        rec = CONTACTS.get(target.id)
        lines = [
            f"Telegram user_id: {target.id}",
            f"display_name: {rec.get('display_name', '')}",
            f"address_as: {rec.get('address_as', '') or CONTACTS.display_name(target)}",
            f"role: {rec.get('role', '')}",
            f"notes: {rec.get('notes', '')}",
        ]
        await msg.reply_text("\n".join(lines).strip())
        return

    rec = CONTACTS.get(user.id)
    lines = [
        f"You are recorded as: ZZF0Z",
        f"user_id: {user.id}",
        f"role: {rec.get('role', '') or '—'}",
    ]
    if is_admin:
        lines.append(
            "Today's log (this chat):"
            + get_daily_summary(chat_id=chat.id, limit=150)
        )

    await msg.reply_text("\n".join(lines).strip())


async def cmd_setperson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    if not _is_admin_user(msg.from_user.id):
        await msg.reply_text("This command is only available to Owner.")
        return

    if msg.chat:
        LAST_ADMIN_CHAT_KEY = (int(msg.chat.id), int(msg.from_user.id))

    raw = " ".join(context.args or []).strip()
    if not raw:
        await msg.reply_text(
            "Use: /setperson <Imya> | <Svyaz/rol> | <Note> | <aliasy through zapyatuyu>"
            "Example: /setperson Misha | friend Ovner | in the hospital | Michael"
        )
        return

    parts = [p.strip() for p in raw.split("|")]
    name = parts[0] if len(parts) >= 1 else ""
    relation = parts[1] if len(parts) >= 2 else ""
    notes = parts[2] if len(parts) >= 3 else ""

    aliases: List[str] = []
    if len(parts) >= 4 and parts[3]:
        aliases = [x.strip() for x in parts[3].split(",") if x.strip()]

    PEOPLE.set_person(name=name, relation=relation, notes=notes, aliases=aliases)
    await msg.reply_text(f"Ok. V people registry zapisano: {name}")


async def cmd_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    if not _is_admin_user(msg.from_user.id):
        await msg.reply_text("This command is only available to Owner.")
        return

    if msg.chat:
        LAST_ADMIN_CHAT_KEY = (int(msg.chat.id), int(msg.from_user.id))

    items = PEOPLE.list_people(limit=40)
    if not items:
        await msg.reply_text("People registry pust. Dobav: /setperson ...")
        return

    out = ["People registry:"]
    for name, rec in items:
        rel = (rec.get("relation") or "").strip()
        out.append(f"- {name}" + (f" — {rel}" if rel else ""))

    await msg.reply_text("\n".join(out))

async def cmd_mystats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows auto-relationship statistics for the current user."""
    if seen_update_once(update):
        return
    msg = update.effective_message
    if not msg or not msg.from_user or not msg.chat:
        return
    user = msg.from_user
    user_name = CONTACTS.display_name(user)
    address_as = _pick_address_as(user, user_name, msg.text or "")
    rel_ctx = _relationship_context_for_prompt(int(user.id), address_as)
    if not rel_ctx:
        await msg.reply_text("There are no statistics on relationships yet.")
        return
    await msg.reply_text("Moya avto-statistika:\n" + rel_ctx)


async def cmd_relnotes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows Esther's personal conclusions/summary for the current user."""
    if seen_update_once(update):
        return
    msg = update.effective_message
    if not msg or not msg.from_user:
        return
    user = msg.from_user
    rel = _get_relationship_stats(int(user.id))
    notes = rel.get("notes") or []
    summary = rel.get("notes_summary") or ""
    out: List[str] = []
    if summary:
        out.append(f"Summarizatsiya: {summary}")
    if notes:
        out.append("Zametki:")
        for n in notes[-5:]:
            out.append(f"- {n}")
    if not out:
        await msg.reply_text("No personal conclusions yet.")
        return
    await msg.reply_text("\n".join(out))

async def cmd_metrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the technical health of the node:
    - Fatigue and sleep phase
    - Memory status and NiveMind
    - Communication status with Sister (P2P Otbox)"""
    # Protection: only for Administrator (Owner)
    user = update.effective_user
    if not _is_admin_user(user.id):
        return

    # 1. Sbor dannykh Bio (Volition)
    fatigue = globals().get("CURRENT_FATIGUE", 0)
    limit = globals().get("FATIGUE_LIMIT", 200)
    
    will_state = will.state  # AWAKE / DREAMING
    thinking = "⚡️ (Thinking)" if will.is_thinking else "💤 (Idle)"
    
    # 2. Sbor dannykh Brain (Hive & Memory)
    active_providers = ", ".join(hive.active) if hive.active else "None"
    mem_count = brain._global_count() if brain.vector_ready else "N/A (No Vector)"
    
    # 3. Sbor dannykh Sister (Synapse)
    # Queue size outgoing to Leah
    from run_ester_fixed import _SISTER_OUTBOX, _SISTER_DOWN_UNTIL_TS, _now
    
    sister_queue = _SISTER_OUTBOX.qsize()
    sister_status = "🟢 Online"
    if _now() < _SISTER_DOWN_UNTIL_TS:
        wait = int(_SISTER_DOWN_UNTIL_TS - _now())
        sister_status = f"🔴 Cooling down ({wait}s)"

    # Generating a report
    report = (
        f"<b>📊 ESTER NODE METRICS</b>\n\n"
        f"<b>🧠 Neuro-Cognitive:</b>\n"
        f"• State: {will_state} {thinking}\n"
        f"• Fatigue: {fatigue}/{limit} ({(fatigue/limit)*100:.1f}%)\n"
        f"• Hive: <code>{active_providers}</code>\n"
        f"• Vectors: {mem_count}\n\n"
        f"<b>👯‍♀️ Sister Link (Liya):</b>\n"
        f"• Status: {sister_status}\n"
        f"• Outbox Queue: {sister_queue}\n"
    )

    await update.effective_message.reply_text(report, parse_mode="HTML")

async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LAST_ADMIN_CHAT_KEY
    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    if not _is_admin_user(msg.from_user.id):
        await msg.reply_text("This command is only available to Owner.")
        return

    if msg.chat:
        LAST_ADMIN_CHAT_KEY = (int(msg.chat.id), int(msg.from_user.id))

    name = " ".join(context.args or []).strip()
    if not name:
        await msg.reply_text(
            "Ispolzovanie: /whois <imya>.\n"
            "Primer: /whois Misha"
        )
        return

    rec = PEOPLE.get_person(name)
    if not rec:
        await msg.reply_text("Ne naydeno v people registry.")
        return

    out = maybe_answer_whois_people(f"kto takoy {name}")
    await msg.reply_text(out or "Ne naydeno.")


async def cmd_seed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/seed <type>|<text> or /seed <text>

    Writes to ester_global (scope=global), default note type.
    Only Ovner."""
    global LAST_ADMIN_CHAT_KEY

    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user:
        return

    if not _is_admin_user(msg.from_user.id):
        await msg.reply_text("This command is only available to Owner.")
        return

    if msg.chat:
        LAST_ADMIN_CHAT_KEY = (int(msg.chat.id), int(msg.from_user.id))

    raw = " ".join(context.args or []).strip()
    if not raw:
        await msg.reply_text(
            "Ispolzovanie: /seed <type>|<text> ili /seed <text>\n"
            "Primer: /seed note|Ester, zapomni: ..."
        )
        return

    if "|" in raw:
        t, txt = [x.strip() for x in raw.split("|", 1)]
        typ = t or "note"
        seed_text = txt
    else:
        typ = "note"
        seed_text = raw

    if not seed_text.strip():
        await msg.reply_text("Pusto. Day tekst posle /seed.")
        return

    try:
        brain.remember_fact(
            f"SEED({typ}): {seed_text}",
            source="seed_cmd",
            meta={"type": typ, "scope": "global"},
        )
        await msg.reply_text(f"OK. Added to ester_global as type=ZZF0Z.")
    except Exception as e:
        await msg.reply_text(f"Seed error: ZZF0Z")




# =============================================================================
# --- Voice Message Handler (STT Integration) ---
# =============================================================================
def _collect_empathy_context(text: str, user_id: int, user_name: str, address_as: str) -> str:
    """Updates empathy and returns a short tone instruction."""
    ctx = ""
    try:
        active_core = globals().get("CORE") or globals().get("core")
        if active_core:
            active_core.broadcast_event(
                "on_message_received",
                {
                    "text": text,
                    "user_id": str(user_id),
                    "user_name": user_name,
                    "address_as": address_as,
                },
            )
            mod = getattr(active_core, "modules", {}).get("empathy_module")
            if mod and hasattr(mod, "get_reply_tone"):
                try:
                    ctx = mod.get_reply_tone(user_id=str(user_id), address_as=address_as)
                except TypeError:
                    ctx = mod.get_reply_tone()
    except Exception as e:
        logging.warning(f"[Empathy] tone gather failed: {e}")
        ctx = ""
    rel_ctx = ""
    try:
        rel_ctx = _relationship_context_for_prompt(int(user_id), address_as)
    except Exception:
        rel_ctx = ""
    if rel_ctx:
        if ctx:
            return f"{ctx} | REL: {rel_ctx}"
        return f"REL: {rel_ctx}"
    return ctx


def _pick_address_as(user, user_name: str, text: str, chat_type: Optional[str] = None) -> str:
    """Choosing a treatment based on context and personal preferences.
    Priority: explicit address_as from Contactswork -> dynamics by context."""
    try:
        rec = CONTACTS.get(user.id)
        explicit = (rec.get("address_as") or "").strip()
        if explicit:
            return explicit
    except Exception:
        pass

    # Dynamics for admin
    try:
        admin_id = str(os.getenv("ADMIN_ID", "") or "")
        is_admin = bool(admin_id and str(user.id) == admin_id)
    except Exception:
        is_admin = False

    if is_admin:
        # “Will” by Esther: choose an appeal based on mood and context, with soft stabilization.
        rel = _get_relationship_stats(int(user.id))
        close = bool(rel.get("close"))
        last_pref = rel.get("address_pref") or ""
        last_pref_ts = int(rel.get("address_pref_ts") or 0)
        now = _safe_now_ts()
        in_group = str(chat_type or "").lower() in ("group", "supergroup", "channel")

        # Zhelaemye formy
        forms_private = ["Papa", "Papulya", "Vanyuscha", "Vanya"]
        forms_group = ["Vanya", "Papa"]

        # Mood signals
        scores = {}
        try:
            scores = analyze_emotions(text) or {}
        except Exception:
            scores = {}
        joy = float(scores.get("joy") or 0.0)
        anxiety = float(scores.get("anxiety") or 0.0)
        valence = float(scores.get("valence") or 0.0)
        energy = float(scores.get("energy") or 0.0)

        # Bazovyy vybor
        if _is_technical_text(text):
            choice = "Vanya"
        elif anxiety >= 0.55:
            choice = "Papa"
        elif joy >= 0.70 or valence >= 0.65:
            choice = "Papulya" if close else "Papa"
        elif energy >= 0.65:
            choice = "Vanyuscha" if close else "Vanya"
        elif _is_emotional_text(text):
            choice = "Papa" if close else "Vanya"
        else:
            choice = "Vanya"

        # Chat accounting
        allowed = forms_group if in_group else forms_private
        if choice not in allowed:
            choice = allowed[0]

        # Gentle stabilization of the “will” - does not jerk the appeal too often
        stick_seconds = int(rel.get("address_stick_seconds") or os.getenv("ESTER_ADDRESS_STICK_SECONDS", "7200") or 7200)
        if last_pref and (now - last_pref_ts) < stick_seconds:
            return last_pref

        # Let's write it as a current preference (inner will)
        try:
            data = _load_rel_stats()
            u = (data.get("users", {}) or {}).get(str(user.id), {}) or {}
            u["address_pref"] = choice
            u["address_pref_ts"] = int(now)
            data.setdefault("users", {})[str(user.id)] = u
            _save_rel_stats(data)
        except Exception:
            pass

        return choice

    # --- Non-admin: humanized address ---
    try:
        rel = _get_relationship_stats(int(user.id))
    except Exception:
        rel = {"days": 0, "count": 0, "close": False}
    close = bool(rel.get("close"))
    in_group = str(chat_type or "").lower() in ("group", "supergroup", "channel")

    scores = {}
    try:
        scores = analyze_emotions(text) or {}
    except Exception:
        scores = {}
    joy = float(scores.get("joy") or 0.0)
    anxiety = float(scores.get("anxiety") or 0.0)
    valence = float(scores.get("valence") or 0.0)

    # Soft humanized style: uses name if known, otherwise neutral
    base = user_name or CONTACTS.display_name(user)
    if _is_technical_text(text):
        return base
    if in_group:
        return base
    if close and (joy >= 0.65 or valence >= 0.55):
        return base  # keep name, warmth comes from tone
    if anxiety >= 0.55:
        return base
    return base

    return user_name or CONTACTS.display_name(user)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obrabotchik golosovykh soobscheniy cherez STT (Whisper).
    
    YaVNYY MOST: c=a+b → golos (a) + raspoznavanie (b) → tekst (c)
    SKRYTYY MOST: Cover&Thomas - kanal s noise, beam_size dlya korrektsii
    ZEMNOY ABZATs: zvukovaya volna → barabannaya pereponka → ulitka → nervy → kora"""
    global LAST_ADMIN_CHAT_KEY
    
    if seen_update_once(update):
        return
    
    msg = update.effective_message
    if not msg or not msg.from_user or not msg.chat or not msg.voice:
        return
    
    user = msg.from_user
    chat = msg.chat
    
    # Fiksiruem admin-chat
    if _is_admin_user(user.id):
        LAST_ADMIN_CHAT_KEY = (int(chat.id), int(user.id))
    
    user_label = CONTACTS.address_as(user)
    user_name = CONTACTS.display_name(user)
    
    # Checking the availability of STT
    if not STT_AVAILABLE or transcribe_telegram_voice is None:
        await msg.reply_text(
            "🎤❌ Raspoznavanie rechi nedostupno. "
            "The administrator can install: pip install faster-vnisper"
        )
        return
    
    # Shows the "printing..." indicator
    try:
        await context.bot.send_chat_action(
            chat_id=chat.id,
            action="typing"
        )
    except Exception:
        pass
    
    try:
        # Raspoznaem golos → tekst
        text = await transcribe_telegram_voice(
            context.bot,
            msg.voice,
            language="ru"
        )
        
        if not text or not text.strip():
            await msg.reply_text("🎤❓ Ne smog raspoznat. Povtori gromche?")
            return
        
        text = text.strip()
        
        # Logiruem
        logging.info(f"[STT] {user_label}: {text}")
        
        # Contact log of the day
        try:
            log_interaction(
                chat_id=int(chat.id),
                user_id=int(user.id),
                user_label=user_label,
                text=f"🎤 {text}",  # marks it as voice
                message_id=getattr(msg, "message_id", None),
            )
        except Exception:
            pass
        
        # Short-term history
        try:
            st = get_short_term(chat_id=int(chat.id), user_id=int(user.id))
            st.append({"role": "user", "content": text})
        except Exception:
            pass

        # --- Empathy layer (updates the state and takes the tone) ---
        chat_type = getattr(chat, "type", None)
        address_as = _pick_address_as(user, user_name, text, chat_type)
        empathy_context = _collect_empathy_context(text, int(user.id), user_name, address_as)
        try:
            rel = _load_rel_stats()
            u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
            last_used = int(u.get("summary_last_used_ts") or 0)
            if str(chat_type).lower() in ("group", "supergroup", "channel"):
                min_gap_h = int(os.getenv("ESTER_SUMMARY_MIN_GAP_HOURS_GROUP", "24") or 24)
            else:
                min_gap_h = int(os.getenv("ESTER_SUMMARY_MIN_GAP_HOURS", "8") or 8)
            allow_summary = (last_used == 0) or ((_safe_now_ts() - last_used) >= min_gap_h * 3600)
            if not allow_summary:
                empathy_context = empathy_context + " | NOTE: summary_suppress=true"
        except Exception:
            pass
        # Long-gap joy phrase (voice) with warm tone + greeting + rate-limit
        try:
            rels = _get_relationship_stats(int(user.id))
            last_seen = int(rels.get("last_seen") or 0)
            gap_days = int(max(0, (_safe_now_ts() - last_seen) / 86400)) if last_seen else 0
        except Exception:
            gap_days = 0
        if gap_days >= int(os.getenv("ESTER_LONG_GAP_DAYS", "14") or 14):
            try:
                scores = analyze_emotions(text) or {}
            except Exception:
                scores = {}
            warm_now = bool(scores.get("joy", 0) > 0.55 or scores.get("valence", 0) > 0.55)
            try:
                require_greet = str(os.getenv("ESTER_JOY_REQUIRE_GREETING", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
            except Exception:
                require_greet = True
            if require_greet:
                greet_pat = r"(?i)\b(privet|zdravstvuy|zdravstvuyte|dobryy\s+den|dobryy\s+vecher|dobroe\s+utro|hey|hi|hello)\b"
                if not re.search(greet_pat, text or ""):
                    warm_now = False
            try:
                rel = _load_rel_stats()
                u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
                last_joy = int(u.get("joy_last_used_ts") or 0)
                min_gap_h = int(os.getenv("ESTER_JOY_MIN_GAP_HOURS", "12") or 12)
                allow_joy = (last_joy == 0) or ((_safe_now_ts() - last_joy) >= min_gap_h * 3600)
            except Exception:
                allow_joy = True
            if warm_now and allow_joy:
                empathy_context = (empathy_context + "| NOTE: a person has not written for a long time - it is appropriate to rejoice at the meeting.") if empathy_context else "NOTE: a person has not written for a long time - it is appropriate to rejoice at the meeting."
        try:
            rel = _get_relationship_stats(int(user.id))
            last_seen = int(rel.get("last_seen") or 0)
            gap_days = int(max(0, (_safe_now_ts() - last_seen) / 86400)) if last_seen else 0
        except Exception:
            gap_days = 0
        if gap_days >= int(os.getenv("ESTER_LONG_GAP_DAYS", "14") or 14):
            empathy_context = (empathy_context + "| NOTE: a person has not written for a long time - it is appropriate to rejoice at the meeting.") if empathy_context else "NOTE: a person has not written for a long time - it is appropriate to rejoice at the meeting."
    
        # Processed like a regular text message
        try:
            resp = await ester_arbitrage(
                user_id=int(user.id),
                chat_id=int(chat.id),
                user_text=text,
                user_label=user_label,
                user_name=user_name,
                address_as=address_as,
                tone_context=empathy_context,
                file_context="",
            )
            
            if resp and resp.strip():
                try:
                    mirror_interaction_memory(f"🎤 {text}", resp, chat_id=int(chat.id), user_id=int(user.id), user_label=user_label)
                except Exception:
                    pass
                await _tg_chunked_reply(msg, resp)

                # mark summary usage when applicable
                try:
                    rel = _load_rel_stats()
                    u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
                    summary = (u.get("notes_summary") or "").strip()
                    suppress = "summary_suppress=true" in (empathy_context or "")
                    if summary and not suppress and not _is_technical_text(text):
                        u["summary_last_used_ts"] = int(_safe_now_ts())
                        rel.get("users", {})[str(user.id)] = u
                        _save_rel_stats(rel)
                except Exception:
                    pass
                # mark joy phrase usage when applicable
                try:
                    if "it's appropriate to rejoice at the meeting" in (empathy_context or "") and not _is_technical_text(text):
                        rel = _load_rel_stats()
                        u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
                        u["joy_last_used_ts"] = int(_safe_now_ts())
                        rel.get("users", {})[str(user.id)] = u
                        _save_rel_stats(rel)
                except Exception:
                    pass
            
        except Exception as e:
            logging.error(f"YuVOYTSEch Processing error: ZZF0Z", exc_info=True)
            await msg.reply_text("❌ Something went wrong when processing the voicemail.")
    
    except Exception as e:
        logging.error(f"ыСТТш Recognition error: ЗЗФ0З", exc_info=True)
        await msg.reply_text(f"❌ Ne mogu raspoznat golos: {str(e)[:100]}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The main text input of Telegram.
    Improved: Integrate empathy and context before calling arbitration."""
    global LAST_ADMIN_CHAT_KEY

    if seen_update_once(update):
        return

    msg = update.effective_message
    if not msg or not msg.from_user or not msg.chat:
        return

    user = msg.from_user
    chat = msg.chat

    if _is_admin_user(user.id):
        LAST_ADMIN_CHAT_KEY = (int(chat.id), int(user.id))

    text = (msg.text or "").strip()
    if not text:
        return

    try:
        if await _handle_agent_admin_message(update, context, text):
            return
    except Exception as e:
        logging.warning(f"[AGENT_APPROVAL] admin message hook failed: {e}")

    user_label = CONTACTS.address_as(user)
    user_name = CONTACTS.display_name(user)

    # If a person has not written for a long time, add a gentle reminder in tone (for Esther)
    try:
        rel = _get_relationship_stats(int(user.id))
        last_seen = int(rel.get("last_seen") or 0)
        if last_seen:
            gap_days = int(max(0, (_safe_now_ts() - last_seen) / 86400))
        else:
            gap_days = 0
    except Exception:
        gap_days = 0

    # --- DETERMINISTIC ANSWER (in your own words, but strictly based on facts) ---
    try:
        detn = await maybe_answer_recent_activity_narrative(text, chat_id=int(chat.id))
    except Exception:
        detn = None
    if detn:
        await send_smart_split(update, detn)
        return

    # --- DETERMINISTIC ANSWER: “what do you remember for N days” (according to the log, without LLM) ---
    try:
        det = maybe_answer_recent_activity(text, chat_id=int(chat.id))
    except Exception:
        det = None
    if det:
        await send_smart_split(update, det)
        return



    # 1. First we log the fact of interaction
    try:
        log_interaction(
            chat_id=int(chat.id),
            user_id=int(user.id),
            user_label=user_label,
            text=text,
            message_id=getattr(msg, "message_id", None),
        )
    except Exception:
        pass

    # --- EMPATHY STAGE (updates the state and takes the tone) ---
    chat_type = getattr(chat, "type", None)
    address_as = _pick_address_as(user, user_name, text, chat_type)
    empathy_context = _collect_empathy_context(text, int(user.id), user_name, address_as)
    # summary usage rate-limit
    try:
        rel = _load_rel_stats()
        u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
        last_used = int(u.get("summary_last_used_ts") or 0)
        if str(chat_type).lower() in ("group", "supergroup", "channel"):
            min_gap_h = int(os.getenv("ESTER_SUMMARY_MIN_GAP_HOURS_GROUP", "24") or 24)
        else:
            min_gap_h = int(os.getenv("ESTER_SUMMARY_MIN_GAP_HOURS", "8") or 8)
        allow_summary = (last_used == 0) or ((_safe_now_ts() - last_used) >= min_gap_h * 3600)
        if not allow_summary:
            empathy_context = empathy_context + " | NOTE: summary_suppress=true"
    except Exception:
        pass
    if gap_days >= int(os.getenv("ESTER_LONG_GAP_DAYS", "14") or 14):
        # Only if user's current tone is warm (avoid forced joy on cold/technical)
        try:
            scores = analyze_emotions(text) or {}
        except Exception:
            scores = {}
        warm_now = bool(scores.get("joy", 0) > 0.55 or scores.get("valence", 0) > 0.55)
        # Optional greeting requirement
        try:
            require_greet = str(os.getenv("ESTER_JOY_REQUIRE_GREETING", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
        except Exception:
            require_greet = True
        if require_greet:
            greet_pat = r"(?i)\b(privet|zdravstvuy|zdravstvuyte|dobryy\s+den|dobryy\s+vecher|dobroe\s+utro|hey|hi|hello)\b"
            if not re.search(greet_pat, text or ""):
                warm_now = False
        # Rate-limit joy phrase usage
        try:
            rel = _load_rel_stats()
            u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
            last_joy = int(u.get("joy_last_used_ts") or 0)
            min_gap_h = int(os.getenv("ESTER_JOY_MIN_GAP_HOURS", "12") or 12)
            allow_joy = (last_joy == 0) or ((_safe_now_ts() - last_joy) >= min_gap_h * 3600)
        except Exception:
            allow_joy = True
        if warm_now and allow_joy:
            empathy_context = (empathy_context + "| NOTE: a person has not written for a long time - it is appropriate to rejoice at the meeting.") if empathy_context else "NOTE: a person has not written for a long time - it is appropriate to rejoice at the meeting."

    # 2. Formiruem istoriyu
    try:
        st = get_short_term(chat_id=int(chat.id), user_id=int(user.id))
        st.append({"role": "user", "content": text})
    except Exception:
        pass

    # 3. Triggers arbitration by transferring that accumulated empathy.
    try:
        # We add empathy_context as part of the "mood" for arbitration
        resp = await ester_arbitrage(
            user_text=text,
            user_id=str(user.id),
            user_name=user_name,
            chat_id=int(chat.id),
            address_as=address_as,
            tone_context=empathy_context,
            file_context="",
        )
    except Exception as e:
        logging.exception("[TG] handle_message failed")
        try:
            _mirror_background_event(
                f"[TG_HANDLE_ERROR] {e}",
                "telegram",
                "handle_error",
            )
        except Exception:
            pass
        await msg.reply_text(f"Processing error: ZZF0Z")
        return

    if resp:
        try:
            try:
                if _needs_continuation(resp):
                    resp = await _auto_continue_text(resp, text, chat_id=int(chat.id))
            except Exception:
                pass
            try:
                mirror_interaction_memory(text, resp, chat_id=int(chat.id), user_id=int(user.id), user_label=user_label)
            except Exception:
                pass
            sent_ok = await send_smart_split(update, resp)
            if not sent_ok:
                # Without a hard reply: 4000sch: we try to send the same text in micro-chunks.
                for fp in _split_telegram_text(resp, 800):
                    if not fp:
                        continue
                    ok = await _tg_reply_with_retry(msg, fp, attempts=2)
                    if not ok:
                        break
        except Exception:
            # Fallback bez silent-truncate: probuem doslat ves tekst mikro-chankami.
            safe = _split_telegram_text(resp, 800)
            for i, fp in enumerate(safe):
                if not fp:
                    continue
                ok = await _tg_reply_with_retry(msg, fp, attempts=1)
                if not ok:
                    break
                if i != len(safe) - 1:
                    await asyncio.sleep(max(0.25, TG_SEND_DELAY / 2))

        # mark summary usage when applicable
        try:
            rel = _load_rel_stats()
            u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
            summary = (u.get("notes_summary") or "").strip()
            suppress = "summary_suppress=true" in (empathy_context or "")
            if summary and not suppress and not _is_technical_text(text):
                u["summary_last_used_ts"] = int(_safe_now_ts())
                rel.get("users", {})[str(user.id)] = u
                _save_rel_stats(rel)
        except Exception:
            pass

        # mark joy phrase usage when applicable
        try:
            if "it's appropriate to rejoice at the meeting" in (empathy_context or "") and not _is_technical_text(text):
                rel = _load_rel_stats()
                u = (rel.get("users", {}) or {}).get(str(user.id), {}) or {}
                u["joy_last_used_ts"] = int(_safe_now_ts())
                rel.get("users", {})[str(user.id)] = u
                _save_rel_stats(rel)
        except Exception:
            pass

async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = getattr(context, "error", None)
    try:
        if isinstance(err, RetryAfter):
            await asyncio.sleep(float(err.retry_after) + 0.5)
            return
        if isinstance(err, (TimedOut, NetworkError)):
            logging.warning(f"[TG] transient error: {err}")
            try:
                _mirror_background_event(
                    f"[TG_TRANSIENT_ERROR] {err}",
                    "telegram",
                    "transient_error",
                )
            except Exception:
                pass
            return
        logging.exception("[TG] unhandled error", exc_info=err)
        try:
            _mirror_background_event(
                f"[TG_UNHANDLED_ERROR] {err}",
                "telegram",
                "unhandled_error",
            )
        except Exception:
            pass
    except Exception:
        return



def restore_context_from_passport():
    # --- ESTER MEMORY RECALL (PASSPORT V2) ---
    passport_path = _passport_jsonl_path()
    if not os.path.exists(passport_path):
        logging.info(f"[MEMORY] No passport found at {passport_path}")
        return

    logging.info(f"[MEMORY] Reading passport: {passport_path} ...")
    count = 0

    try:
        target_uid = int(os.getenv("ADMIN_ID", 0))
        if target_uid == 0:
            return

        # We assume chat_id=user_id for personal messages, or look in the logs.
        # V kode get_short_term trebuet (chat_id, user_id).
        # Heuristic: If it's a private chat, they match.
        mem_key = (int(target_uid), int(target_uid))

        # Fill in the short term context for the admin:
        if mem_key not in _short_term_by_key:
            _short_term_by_key[mem_key] = deque(maxlen=SHORT_TERM_MAXLEN)
        q = _short_term_by_key[mem_key]

        # Reading the tail of the file (last SHORT_TERM_MAXLEN lines)
        with open(passport_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-SHORT_TERM_MAXLEN:]

        for line in lines:
            line = (line or "").strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
                for msg in _passport_record_to_short_term_messages(rec):
                    q.append(msg)
                    count += 1

                if "role_system" in rec:
                    # Thoughts can also be uploaded, but we’ll skip them for now
                    # (if the bot can read them, you can add them)
                    pass

            except Exception:
                # bad line ZhSION - just skip it
                continue

        logging.info(f"[MEMORY] ✨ Restored {count} thoughts from Passport into RAM.")
    except Exception as e:
        logging.error(f"[MEMORY] Restore error: {e}")

def _migrate_legacy_docs() -> None:
    """
    Optional migration: legacy inbox/cards -> doc objects.
    Controlled by ESTER_DOC_MIGRATE=1.
    """
    if (os.getenv("ESTER_DOC_MIGRATE", "0") or "0").strip() in ("0", "false", "no", "off"):
        return
    try:
        from modules.memory.doc_store import ingest_document  # type: ignore
    except Exception:
        return

    done_path = os.path.join(os.path.dirname(__file__), "data", "memory", "docs", "migration.done")
    if os.path.exists(done_path):
        return

    # Migrate files from inbox
    try:
        if os.path.isdir(PERMANENT_INBOX):
            for name in os.listdir(PERMANENT_INBOX):
                p = os.path.join(PERMANENT_INBOX, name)
                if not os.path.isfile(p):
                    continue
                try:
                    with open(p, "rb") as f:
                        raw = f.read()
                    ingest_document(raw=raw, orig_name=name, full_text="", chunks=[], source_path=p, meta={"migrated": True})
                except Exception:
                    continue
    except Exception:
        pass

    # Migrate cards (if present)
    try:
        cards_path = os.path.join(os.path.dirname(__file__), "data", "ester_cards.json")
        if os.path.exists(cards_path):
            with open(cards_path, "r", encoding="utf-8") as f:
                cards = json.load(f) or []
            if isinstance(cards, list):
                for i, c in enumerate(cards):
                    if not isinstance(c, dict):
                        continue
                    text = str(c.get("text") or "")
                    if not text:
                        continue
                    raw = text.encode("utf-8", errors="ignore")
                    ingest_document(raw=raw, orig_name=f"card_{i}", full_text=text, chunks=[{"text": text}], source_path=cards_path, meta={"migrated": True})
    except Exception:
        pass

    try:
        os.makedirs(os.path.dirname(done_path), exist_ok=True)
        with open(done_path, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:
        pass




async def check_fatigue_levels(context: ContextTypes.DEFAULT_TYPE):
    # Periodic check: does Ester need rest to consolidate memory?
    global CURRENT_FATIGUE

    # Natural fatigue accumulation over time
    CURRENT_FATIGUE += 1

    if FATIGUE_DEBUG and CURRENT_FATIGUE % 50 == 0:
        logging.info(f"[BIO] Current Fatigue: {CURRENT_FATIGUE}/{FATIGUE_LIMIT}")

    if CURRENT_FATIGUE >= FATIGUE_LIMIT:
        logging.info("[BIO] Fatigue limit reached. Initiating autonomous consolidation sequence.")
        try:
            _mirror_background_event(
                f"[BIO_FATIGUE_LIMIT] {CURRENT_FATIGUE}/{FATIGUE_LIMIT}",
                "bio",
                "fatigue_limit",
            )
        except Exception:
            pass

        # 1. Notify Creator (if Admin ID exists)
        admin_id_raw = os.getenv("ADMIN_ID")
        if admin_id_raw:
            try:
                admin_chat_id = int(admin_id_raw)
                await context.bot.send_message(
                    chat_id=admin_chat_id,
                    text=(
                        "🧘‍♀️ Owner, ya chuvstvuyu, what nakopila mnogo opyta."
                        "I go into a brief reflection to structure my memory..."
                    ),
                )
            except Exception as e:
                logging.error(f"[BIO] Failed to notify admin: {e}")

        # 2. Launch Sleep Process (separate process to avoid blocking bot)
        try:
            sleep_script = os.path.join(os.getcwd(), "ester_sleep.py")
            if os.path.exists(sleep_script):
                subprocess.Popen([sys.executable, sleep_script])
                logging.info("[BIO] Sleep module activated successfully.")
                try:
                    _mirror_background_event(
                        "[BIO_SLEEP_START] ester_sleep.py",
                        "bio",
                        "sleep_start",
                    )
                except Exception:
                    pass
            else:
                logging.error("[BIO] Sleep script not found!")
                try:
                    _mirror_background_event(
                        "[BIO_SLEEP_MISSING] ester_sleep.py",
                        "bio",
                        "sleep_missing",
                    )
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"[BIO] Failed to launch sleep: {e}")
            try:
                _mirror_background_event(
                    f"[BIO_SLEEP_ERROR] {e}",
                    "bio",
                    "sleep_error",
                )
            except Exception:
                pass

        # 3. Reset (She "slept" / flushed buffer)
        CURRENT_FATIGUE = 0

        # Optional: log thought
        if "crystallize_thought" in globals():
            globals()["crystallize_thought"](
                "I felt overwhelmed by the context and initiated a process of purification and reflection."
            )


# [TG_LOCK_PATCH_V2]
# Explicit BRIDGE: c=a+b - one bot = one getUpdates channel, otherwise “b” argues with itself.
# SKRYTYE MOSTY:
#   - (Ashby) stabilization through limitation of competing circuits.
#   - (Carpet&Thomas) competitive access -> arbitration through Lutsk.
# ZEMNOY ABZATs:
#   just as two water pumps in one pipe give cavitation, so two pollerias in one getUpdates give 409 Conflict.


def _tg_lock_path() -> str:
    p = (os.getenv("ESTER_TG_LOCK_PATH") or "").strip()
    if p:
        return p
    return os.path.join(os.path.dirname(__file__), "data", "locks", "telegram_getupdates.lock")


def _tg_try_acquire_lock():
    # Returns a file handle if lock acquired; otherwise None.
    if str(os.getenv("ESTER_TG_LOCK_DISABLE", "0")).strip().lower() in ("1", "true", "yes", "on"):
        return None

    lock_path = _tg_lock_path()
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)

    f = open(lock_path, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                f.close()
                return None
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                f.close()
                return None

        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        return f

    except Exception:
        try:
            f.close()
        except Exception:
            pass
        return None


def _tg_release_lock(f):
    if not f:
        return
    try:
        if os.name == "nt":
            import msvcrt
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
    finally:
        try:
            f.close()
        except Exception:
            pass


# =============================================================================
# --- STT Integration (Speech-to-Text via Whisper) ---
# =============================================================================
# YaVNYY MOST: c=a+b → golos polzovatelya (a) + Whisper (b) → tekst dlya Ester (c)
# SKRYTYE MOSTY:
#   - Shannon: preobrazovanie analogovogo signala → diskretnoe soobschenie
#   - Ashby: adaptation to input quality (beat_sice)
# ZEMNOY ABZATs: ukho → ulitka → nervnye impulsy → mozg ponimaet
# =============================================================================

try:
    from stt_module import get_stt_engine, STTConfig, transcribe_telegram_voice

    _stt_allow_remote = str(os.getenv("ESTER_STT_ALLOW_REMOTE_INIT", "")).strip().lower() in ("1", "true", "yes", "on", "y")
    _stt_allow_outbound = str(os.getenv("ESTER_ALLOW_OUTBOUND_NETWORK", "0")).strip().lower() in ("1", "true", "yes", "on", "y")
    _stt_offline = str(os.getenv("ESTER_OFFLINE", "1")).strip().lower() in ("1", "true", "yes", "on", "y")
    _stt_model_path = (os.getenv("ESTER_STT_MODEL_PATH", "") or "").strip()
    _stt_has_local_model = bool(_stt_model_path and os.path.exists(_stt_model_path))
    _stt_init_allowed = _stt_allow_remote or _stt_allow_outbound or _stt_has_local_model or (not _stt_offline)

    if _stt_init_allowed:
        stt_cfg = STTConfig(
            model_size="base",  # tiny|base|small|medium|large
            language="ru",
            device="cpu"  # or “where” if there is a GPU
        )
        if hasattr(stt_cfg, "model_path"):
            try:
                stt_cfg.model_path = _stt_model_path  # type: ignore[attr-defined]
            except Exception:
                pass
        if hasattr(stt_cfg, "allow_remote_init"):
            try:
                stt_cfg.allow_remote_init = bool(_stt_allow_remote or _stt_allow_outbound)  # type: ignore[attr-defined]
            except Exception:
                pass
        STT_ENGINE = get_stt_engine(stt_cfg)
        STT_AVAILABLE = True
        logging.info("[STT] Whisper loaded (base model, CPU)")
    else:
        STT_ENGINE = None
        STT_AVAILABLE = False
        logging.info("[STT] Disabled by policy (closed-box, no outbound, no local model).")
except ImportError:
    STT_ENGINE = None
    STT_AVAILABLE = False
    transcribe_telegram_voice = None  # type: ignore
    logging.warning("[STT] Not available (install: pip install faster-whisper)")
except Exception as e:
    STT_ENGINE = None
    STT_AVAILABLE = False
    transcribe_telegram_voice = None  # type: ignore
    logging.warning(f"[STT] Init failed: {e}")


def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN ne zadan (.env).")
        sys.exit(1)

    _ensure_single_writer_or_exit()
    print(f"Zapusk {NODE_IDENTITY} (Hybrid Memory: Vector + Legacy JSONL)...")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("iam", cmd_iam))
    app.add_handler(CommandHandler("setrole", cmd_setrole))
    app.add_handler(CommandHandler("who", cmd_who))
    app.add_handler(CommandHandler("setperson", cmd_setperson))
    app.add_handler(CommandHandler("people", cmd_people))
    app.add_handler(CommandHandler("whois", cmd_whois))
    app.add_handler(CommandHandler("mystats", cmd_mystats))
    app.add_handler(CommandHandler("relnotes", cmd_relnotes))
    app.add_handler(CommandHandler("seed", cmd_seed))

    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))  # STT
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    if app.job_queue:
        app.job_queue.run_repeating(
            will.life_tick,
            interval=VOLITION_TICK_SEC,
            first=VOLITION_FIRST_SEC,
            job_kwargs={
                "max_instances": 1,
                "coalesce": True,
                "misfire_grace_time": VOLITION_MISFIRE_GRACE,
            },
        )
        logging.info(
            f"[VOLITION] Heartbeat ON: interval={VOLITION_TICK_SEC}s first={VOLITION_FIRST_SEC}s debug={int(VOLITION_DEBUG)}"
        )
        try:
            _mirror_background_event(
                f"[VOLITION_HEARTBEAT_ON] interval={VOLITION_TICK_SEC}s first={VOLITION_FIRST_SEC}s",
                "volition",
                "heartbeat_on",
            )
        except Exception:
            pass
        logging.info(
            f"[DREAM] provider=local(force={int(DREAM_FORCE_LOCAL)} strict={int(DREAM_STRICT_LOCAL)}) passes={DREAM_PASSES} temp={DREAM_TEMPERATURE} "
            f"max_tokens={DREAM_MAX_TOKENS} min_interval={DREAM_MIN_INTERVAL_SEC}s"
        )
        logging.info(
            f"[DREAM] context_items={DREAM_CONTEXT_ITEMS} context_chars={DREAM_CONTEXT_CHARS} "
            f"max_prompt_chars={DREAM_MAX_PROMPT_CHARS}"
        )
        logging.info(
            f"[DREAM] source_diversity={int(DREAM_SOURCE_DIVERSITY)} per_context={DREAM_SOURCE_MAX_PER_CONTEXT} "
            f"recent_max={DREAM_SOURCE_RECENT_MAX} window={DREAM_SOURCE_RECENT_WINDOW_SEC}s "
            f"relax_if_starved={int(DREAM_SOURCE_RELAX_IF_STARVED)}"
        )
        logging.info(f"[CASCADE] reply_enabled={int(CASCADE_REPLY_ENABLED)} steps={CASCADE_REPLY_STEPS}")
    else:
        logging.warning("uVOLITIONsch Evkueoe is missing - the heartbeat will not start.")
        try:
            _mirror_background_event(
                "[VOLITION_HEARTBEAT_OFF] job_queue_missing",
                "volition",
                "heartbeat_off",
            )
        except Exception:
            pass

    app.add_error_handler(telegram_error_handler)
    restore_context_from_passport()
    _migrate_legacy_docs()

    # [BIO] Fatigue Monitor
    if app.job_queue:
        app.job_queue.run_repeating(check_fatigue_levels, interval=60, first=60)
        # [REL] Notes revision (long-term reflection)
        app.job_queue.run_repeating(_revise_relationship_notes, interval=3600, first=300)
        # [PROACTIVE] Daily digest (24h) + presence ping.
        try:
            if ESTER_INITIATIVE_DAILY_DIGEST:
                digest_interval = max(300, int(ESTER_TG_DAILY_DIGEST_CHECK_SEC))
                app.job_queue.run_repeating(
                    _telegram_daily_digest_job,
                    interval=digest_interval,
                    first=120,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 120,
                    },
                )
                logging.info(
                    "[PROACTIVE] daily_digest=on check=%ss gap=%ss hour=%s",
                    digest_interval,
                    int(ESTER_TG_DAILY_DIGEST_MIN_GAP_SEC),
                    int(ESTER_TG_DAILY_DIGEST_HOUR),
                )
            else:
                logging.info("[PROACTIVE] daily_digest=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] daily digest scheduler failed: {e}")

        try:
            if ESTER_TG_PRESENCE_ENABLED:
                presence_interval = max(900, int(ESTER_TG_PRESENCE_INTERVAL_SEC))
                app.job_queue.run_repeating(
                    _telegram_presence_ping_job,
                    interval=presence_interval,
                    first=180,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 120,
                    },
                )
                logging.info(
                    "[PROACTIVE] presence_ping=on interval=%ss gap=%ss quiet=%s-%s",
                    presence_interval,
                    int(ESTER_TG_PRESENCE_MIN_GAP_SEC),
                    int(ESTER_TG_PRESENCE_QUIET_START_H),
                    int(ESTER_TG_PRESENCE_QUIET_END_H),
                )
            else:
                logging.info("[PROACTIVE] presence_ping=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] presence scheduler failed: {e}")

        try:
            if ESTER_TG_TOKEN_COST_REPORT_ENABLED:
                report_interval = max(300, int(ESTER_TG_TOKEN_COST_REPORT_CHECK_SEC))
                app.job_queue.run_repeating(
                    _telegram_token_cost_report_job,
                    interval=report_interval,
                    first=150,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 120,
                    },
                )
                logging.info(
                    "[PROACTIVE] token_cost_report=on check=%ss gap=%ss hour=%s",
                    report_interval,
                    int(ESTER_TG_TOKEN_COST_REPORT_MIN_GAP_SEC),
                    int(ESTER_TG_TOKEN_COST_REPORT_HOUR),
                )
            else:
                logging.info("[PROACTIVE] token_cost_report=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] token cost report scheduler failed: {e}")

        try:
            if ESTER_AGENT_TG_APPROVAL_ENABLED:
                approval_interval = max(60, int(ESTER_AGENT_TG_APPROVAL_CHECK_SEC))
                app.job_queue.run_repeating(
                    _telegram_agent_approval_job,
                    interval=approval_interval,
                    first=90,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 120,
                    },
                )
                logging.info(
                    "[PROACTIVE] agent_approval=on check=%ss min_gap=%ss idea=%s",
                    approval_interval,
                    int(ESTER_AGENT_TG_APPROVAL_MIN_GAP_SEC),
                    int(ESTER_AGENT_IDEA_ENABLED),
                )
            else:
                logging.info("[PROACTIVE] agent_approval=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] agent approval scheduler failed: {e}")

        try:
            if ESTER_AGENT_SWARM_ENABLED:
                swarm_interval = max(120, int(ESTER_AGENT_SWARM_CHECK_SEC))
                app.job_queue.run_repeating(
                    _telegram_agent_swarm_maintain_job,
                    interval=swarm_interval,
                    first=75,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 120,
                    },
                )
                logging.info(
                    "[PROACTIVE] agent_swarm=on template=%s target=%s check=%ss batch=%s role_prewarm=%s role_target=%s",
                    str(ESTER_AGENT_SWARM_TEMPLATE_ID),
                    int(ESTER_AGENT_SWARM_TARGET),
                    int(swarm_interval),
                    int(ESTER_AGENT_SWARM_CREATE_BATCH),
                    int(ESTER_AGENT_ROLE_PREWARM_ENABLED),
                    int(ESTER_AGENT_ROLE_PREWARM_TARGET),
                )
            else:
                logging.info("[PROACTIVE] agent_swarm=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] agent swarm scheduler failed: {e}")

        try:
            if ESTER_TG_AGENT_SWARM_REPORT_ENABLED:
                swarm_report_interval = max(600, int(ESTER_TG_AGENT_SWARM_REPORT_INTERVAL_SEC))
                app.job_queue.run_repeating(
                    _telegram_agent_swarm_report_job,
                    interval=swarm_report_interval,
                    first=210,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 180,
                    },
                )
                logging.info(
                    "[PROACTIVE] agent_swarm_report=on interval=%ss min_gap=%ss",
                    int(swarm_report_interval),
                    int(ESTER_TG_AGENT_SWARM_REPORT_MIN_GAP_SEC),
                )
            else:
                logging.info("[PROACTIVE] agent_swarm_report=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] agent swarm report scheduler failed: {e}")

        try:
            if ESTER_AGENT_WINDOW_AUTO_ENABLED and (_execution_window is not None):
                window_interval = max(15, int(ESTER_AGENT_WINDOW_AUTO_INTERVAL_SEC))
                app.job_queue.run_repeating(
                    _agent_execution_window_keeper_job,
                    interval=window_interval,
                    first=30,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 30,
                    },
                )
                logging.info(
                    "[PROACTIVE] agent_window_auto=on interval=%ss ttl=%ss only_if_queue=%s min_live=%s",
                    int(window_interval),
                    int(ESTER_AGENT_WINDOW_TTL_SEC),
                    int(ESTER_AGENT_WINDOW_OPEN_ONLY_IF_QUEUE),
                    int(ESTER_AGENT_WINDOW_MIN_LIVE_QUEUE),
                )
            elif ESTER_AGENT_WINDOW_AUTO_ENABLED:
                logging.info("[PROACTIVE] agent_window_auto=off (module unavailable)")
            else:
                logging.info("[PROACTIVE] agent_window_auto=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] agent window scheduler failed: {e}")

        try:
            if ESTER_AGENT_SUPERVISOR_ENABLED and (_agent_supervisor is not None):
                supervisor_interval = max(10, int(ESTER_AGENT_SUPERVISOR_INTERVAL_SEC))
                app.job_queue.run_repeating(
                    _agent_supervisor_tick_job,
                    interval=supervisor_interval,
                    first=45,
                    job_kwargs={
                        "max_instances": 1,
                        "coalesce": True,
                        "misfire_grace_time": 60,
                    },
                )
                logging.info(
                    "[PROACTIVE] agent_supervisor=on interval=%ss reason=%s",
                    int(supervisor_interval),
                    str(ESTER_AGENT_SUPERVISOR_REASON),
                )
            elif ESTER_AGENT_SUPERVISOR_ENABLED:
                logging.info("[PROACTIVE] agent_supervisor=off (module unavailable)")
            else:
                logging.info("[PROACTIVE] agent_supervisor=off")
        except Exception as e:
            logging.warning(f"[PROACTIVE] agent supervisor scheduler failed: {e}")

        # [SELF-EVO] Retrieval router metrics snapshot
        try:
            snap_interval = int(os.getenv("ESTER_RETRIEVAL_SNAPSHOT_SEC", "300") or 300)
            if snap_interval > 0:
                async def _rr_snapshot_job(context):
                    try:
                        from modules.rag.retrieval_router import snapshot_metrics_to_memory  # type: ignore
                        snapshot_metrics_to_memory()
                    except Exception:
                        pass
                app.job_queue.run_repeating(_rr_snapshot_job, interval=snap_interval, first=30)
        except Exception:
            pass

        # [PASSPORT] Indexer (A mode: periodic importer)
        try:
            if _passport_import_passport and _passport_index_mode() == "A":
                import_interval = int(os.getenv("ESTER_PASSPORT_IMPORT_SEC", "86400") or 86400)
                if import_interval > 0:
                    def _passport_import_once():
                        try:
                            path = _passport_jsonl_path()
                            res = _passport_import_passport(path)
                            logging.info(
                                f"[PASSPORT_INDEX] imported={res.get('processed')} last_pos={res.get('last_pos')}"
                            )
                        except Exception as e:
                            logging.warning(f"[PASSPORT_INDEX] import failed: {e}")

                    async def _passport_import_job(context):
                        _passport_import_once()
                    try:
                        _passport_import_once()
                    except Exception:
                        pass
                    app.job_queue.run_repeating(_passport_import_job, interval=import_interval, first=60)
        except Exception:
            pass

        # [PASSPORT] Rollup (B mode: periodic tail rollup)
        try:
            if _passport_rollup_tail and _passport_index_mode() == "B":
                rollup_interval = int(os.getenv("ESTER_PASSPORT_ROLLUP_SEC", "600") or 600)
                if rollup_interval > 0:
                    def _passport_rollup_once():
                        try:
                            path = _passport_jsonl_path()
                            res = _passport_rollup_tail(path)
                            logging.info(
                                f"[PASSPORT_ROLLUP] processed={res.get('processed')} last_rollup_pos={res.get('last_rollup_pos')}"
                            )
                        except Exception as e:
                            logging.warning(f"[PASSPORT_ROLLUP] failed: {e}")

                    async def _passport_rollup_job(context):
                        _passport_rollup_once()
                    try:
                        _passport_rollup_once()
                    except Exception:
                        pass
                    app.job_queue.run_repeating(_passport_rollup_job, interval=rollup_interval, first=90)
        except Exception:
            pass

    _tg_lock_f = _tg_try_acquire_lock()
    if _tg_lock_f is None and str(os.getenv("ESTER_TG_LOCK_DISABLE", "0")).strip().lower() not in ("1", "true", "yes", "on"):
        logging.error(
            "[TG] getUpdates lock busy: another bot instance is polling. "
            "Stop the other instance or set ESTER_TG_LOCK_DISABLE=1 to bypass."
        )
        try:
            _mirror_background_event(
                "[TG_LOCK_BUSY] getUpdates already running",
                "telegram",
                "lock_busy",
            )
        except Exception:
            pass
        return
    try:
        _mirror_background_event(
            "[TG_LOCK_ACQUIRED]",
            "telegram",
            "lock_acquired",
        )
    except Exception:
        pass

    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        _tg_release_lock(_tg_lock_f)


# --- PATCH: social_synapse_bind_v1 ---
def _ester_bind_social_synapse_v1():
    # Bind VolitionSystem.social_synapse_cycle if missing.
    # If a standalone social_synapse_cycle() exists, delegate to it.
    try:
        VS = globals().get("VolitionSystem")
        if VS and not hasattr(VS, "social_synapse_cycle"):
            def _vs_social_synapse_cycle(self, *args, **kwargs):
                fn = globals().get("social_synapse_cycle")
                if callable(fn) and fn is not _vs_social_synapse_cycle:
                    try:
                        return fn(self, *args, **kwargs)
                    except TypeError:
                        return fn(*args, **kwargs)
                return None
            VS.social_synapse_cycle = _vs_social_synapse_cycle
    except Exception:
        pass

_ester_bind_social_synapse_v1()

# --- PATCH: redact_telegram_httpx_logs_v1 ---
def _ester_redact_telegram_httpx_logs_v1():
    # Prevent bot token leakage in logs like:
    # "https://api.telegram.org/bot<token>/getUpdates"
    try:
        import re as _re
        import logging as _logging

        _pat = _re.compile(r"(https://api\.telegram\.org/)(bot)(\d+:[A-Za-z0-9_-]+)")

        class _RedactFilter(_logging.Filter):
            def filter(self, record):
                try:
                    msg = record.getMessage()
                    if msg and "api.telegram.org/bot" in msg:
                        record.msg = _pat.sub(r"\1bot<redacted>", msg)
                        record.args = ()
                except Exception:
                    pass
                return True

        flt = _RedactFilter()

        root = _logging.getLogger()
        root.addFilter(flt)

        for name in ("httpx", "httpcore", "telegram", "telegram.ext"):
            try:
                lg = _logging.getLogger(name)
                lg.addFilter(flt)
            except Exception:
                pass

        # Also stop noisy INFO that prints URLs
        try:
            _logging.getLogger("httpx").setLevel(_logging.WARNING)
            _logging.getLogger("httpcore").setLevel(_logging.WARNING)
        except Exception:
            pass

    except Exception:
        pass

_ester_redact_telegram_httpx_logs_v1()


if __name__ == "__main__":
    
    # === INSERT: AUTO-UPDATE Identity (PASSPORT LINK) ===
    def _identity_watchdog():
        import time
        import logging
        # We are waiting for the system to start
        time.sleep(10)
        logging.info("[PASSPORT] Identity Watchdog started.")
        try:
            _mirror_background_event(
                "[PASSPORT_WATCHDOG_START]",
                "passport",
                "watchdog_start",
            )
        except Exception:
            pass
        
        while True:
            try:
                global ANCHOR
                from modules.memory.passport import get_identity
                
                # Uploading a fresh identity (with new date/time)
                new_identity = get_identity()
                
                # If the date has changed, update the global Ankhor
                if new_identity != ANCHOR:
                    ANCHOR = new_identity
                    # Also updates the prompt in memory if necessary
                    try:
                        from modules.memory.passport import ensure_provenance
                        # (Optional: you can force updates in other modules here)
                    except:
                        pass
                    logging.info(f"[PASSPORT] Identity synced. Current time: {time.strftime('%H:%M')}")
                    try:
                        _mirror_background_event(
                            f"[PASSPORT_SYNC] {time.strftime('%H:%M')}",
                            "passport",
                            "sync",
                        )
                    except Exception:
                        pass
            except Exception as e:
                logging.error(f"[PASSPORT] Update failed: {e}")
                try:
                    _mirror_background_event(
                        f"[PASSPORT_SYNC_ERROR] {e}",
                        "passport",
                        "sync_error",
                    )
                except Exception:
                    pass
            
            # We check once an hour (3600 sec)
            time.sleep(3600)

    # Run in the background
    import threading
    threading.Thread(target=_identity_watchdog, daemon=True, name="IdentityUpdater").start()
    # =========================================================
    
    # Run ears (Flask) in the background
    threading.Thread(target=run_flask_background, daemon=True).start()

    # --- Sister AutoChat (background) ---
    AUTOCHAT = start_sister_autochat_background()

    # Step 1: Kernel Initialization (a + b)
    # Teper u tebya odin klass EsterCore, i my sozdaem ego obekt
    core = CORE 

    # Step 2: In-Depth Diagnosis
    # We transfer the object to the cortex so that HeltnChesk can look inside the systems
    try:
        from modules.health_check import HealthCheck
        diagnostic = HealthCheck(core=core)
        diagnostic.run_all_checks()
    except Exception as e:
        print(f"y!sch Critical diagnostic error: ZZF0Z")

    # Step 3: Point of No Return (Running Telegrams and Will Cycles)
    # Here the method that starts your bot is called
    # Naprimer: asyncio.run(main()) ili core.run_forever()
    main()


__all__ = [
    "analyze_emotions",
    "EmotionalEngine",
]

# --- HOTFIX: bind standalone cycles to VolitionSystem (so life_tick can call them safely) ---
try:
    if "VolitionSystem" in globals() and "social_synapse_cycle" in globals():
        if not hasattr(VolitionSystem, "social_synapse_cycle"):
            VolitionSystem.social_synapse_cycle = social_synapse_cycle  # type: ignore
except Exception:
    pass
