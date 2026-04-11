from __future__ import annotations

import json
import os
import threading
import time
import unicodedata
from typing import Any, Dict, List, Optional


_LOCK = threading.RLock()


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _store_path() -> str:
    return os.path.join(_state_root(), "data", "memory", "recent_chat_docs.json")


def _default_store() -> Dict[str, Any]:
    return {"version": 2, "updated_at": 0, "by_chat": {}, "bindings": {}}


def _trim_text(text: str, max_chars: int) -> str:
    s = str(text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _normalize_name(name: str) -> str:
    s = unicodedata.normalize("NFKC", str(name or ""))
    s = s.replace("\\", "/").split("/")[-1]
    s = " ".join(s.split()).strip().casefold()
    return s.strip(" ._-\"'`“”«»")


def _load_store_unlocked() -> Dict[str, Any]:
    path = _store_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            data.setdefault("version", 2)
            data.setdefault("updated_at", 0)
            data.setdefault("by_chat", {})
            data.setdefault("bindings", {})
            if isinstance(data.get("by_chat"), dict):
                if not isinstance(data.get("bindings"), dict):
                    data["bindings"] = {}
                return data
    except Exception:
        pass
    return _default_store()


def _save_store_unlocked(store: Dict[str, Any]) -> None:
    path = _store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _same_doc(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    a_doc_id = str(a.get("doc_id") or "").strip()
    b_doc_id = str(b.get("doc_id") or "").strip()
    if a_doc_id and b_doc_id:
        return a_doc_id == b_doc_id
    a_name = _normalize_name(str(a.get("name") or ""))
    b_name = _normalize_name(str(b.get("name") or ""))
    if a_name and b_name:
        return a_name == b_name
    return False


def _binding_key(chat_id: Optional[int], user_id: Optional[int]) -> str:
    if chat_id is None:
        return ""
    return f"{int(chat_id)}:{'' if user_id is None else int(user_id)}"


def _binding_ttl(ttl_sec: Optional[int] = None) -> int:
    try:
        ttl = int(
            ttl_sec
            if ttl_sec is not None
            else (os.getenv("RECENT_DOC_BINDING_TTL_SEC", "86400") or 86400)
        )
    except Exception:
        ttl = 86400
    return max(300, ttl)


def _prune_bindings_unlocked(store: Dict[str, Any], ttl_sec: Optional[int] = None) -> bool:
    bindings = store.setdefault("bindings", {})
    if not isinstance(bindings, dict):
        store["bindings"] = {}
        return True
    ttl = _binding_ttl(ttl_sec)
    now = int(time.time())
    fresh: Dict[str, Dict[str, Any]] = {}
    changed = False
    for key, value in bindings.items():
        if not isinstance(value, dict):
            changed = True
            continue
        try:
            ts = int(value.get("ts") or 0)
        except Exception:
            ts = 0
        if ts > 0 and (now - ts) <= ttl:
            fresh[str(key)] = value
        else:
            changed = True
    if changed:
        store["bindings"] = fresh
    return changed


def remember_recent_doc(
    chat_id: Optional[int],
    *,
    doc_id: str,
    name: str,
    summary: str,
    citations: List[str],
    source_path: str = "",
) -> Dict[str, Any]:
    if chat_id is None:
        return {}

    try:
        max_per_chat = max(1, int(os.getenv("RECENT_DOC_MAX_PER_CHAT", "8") or 8))
    except Exception:
        max_per_chat = 8

    rec = {
        "ts": int(time.time()),
        "doc_id": str(doc_id or "").strip(),
        "name": str(name or "").strip(),
        "summary": _trim_text(summary or "", 2600),
        "citations": [str(c or "").strip() for c in (citations or []) if str(c or "").strip()][:12],
        "source_path": str(source_path or "").strip(),
    }

    with _LOCK:
        store = _load_store_unlocked()
        by_chat = store.setdefault("by_chat", {})
        key = str(chat_id)
        entries = list(by_chat.get(key) or [])
        entries = [item for item in entries if isinstance(item, dict) and not _same_doc(item, rec)]
        entries.insert(0, rec)
        by_chat[key] = entries[:max_per_chat]
        store["updated_at"] = int(time.time())
        _save_store_unlocked(store)
    return rec


def remember_last_resolved_document(
    chat_id: Optional[int],
    user_id: Optional[int],
    *,
    doc_id: str,
    orig_name: str = "",
    title: str = "",
    source_path: str = "",
    passport_path: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    key = _binding_key(chat_id, user_id)
    doc_id_s = str(doc_id or "").strip()
    if not key or not doc_id_s:
        return {}

    rec = {
        "ts": int(time.time()),
        "doc_id": doc_id_s,
        "orig_name": str(orig_name or "").strip(),
        "title": str(title or "").strip(),
        "source_path": str(source_path or "").strip(),
        "passport_path": str(passport_path or "").strip(),
        "reason": str(reason or "").strip(),
    }

    with _LOCK:
        store = _load_store_unlocked()
        _prune_bindings_unlocked(store)
        bindings = store.setdefault("bindings", {})
        bindings[key] = rec
        store["updated_at"] = int(time.time())
        _save_store_unlocked(store)
    return rec


def get_last_resolved_document(
    chat_id: Optional[int],
    user_id: Optional[int],
    ttl_sec: Optional[int] = None,
) -> Dict[str, Any]:
    key = _binding_key(chat_id, user_id)
    if not key:
        return {}

    with _LOCK:
        store = _load_store_unlocked()
        changed = _prune_bindings_unlocked(store, ttl_sec=ttl_sec)
        bindings = store.setdefault("bindings", {})
        out = dict(bindings.get(key) or {})
        if not out and user_id is not None:
            out = dict(bindings.get(_binding_key(chat_id, None)) or {})
        if changed:
            store["updated_at"] = int(time.time())
            _save_store_unlocked(store)
        return out


def find_recent_doc_entry(
    chat_id: Optional[int],
    doc_id: str,
    ttl_sec: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    did = str(doc_id or "").strip()
    if not did:
        return None
    for item in list_recent_docs(chat_id, ttl_sec=ttl_sec):
        if str(item.get("doc_id") or "").strip() == did:
            return dict(item)
    return None


def list_recent_docs(chat_id: Optional[int], ttl_sec: Optional[int] = None) -> List[Dict[str, Any]]:
    if chat_id is None:
        return []

    try:
        ttl = int(ttl_sec if ttl_sec is not None else (os.getenv("RECENT_DOC_TTL_SEC", "21600") or 21600))
    except Exception:
        ttl = 21600
    ttl = max(300, ttl)
    now = int(time.time())

    with _LOCK:
        store = _load_store_unlocked()
        by_chat = store.setdefault("by_chat", {})
        key = str(chat_id)
        entries = [item for item in list(by_chat.get(key) or []) if isinstance(item, dict)]
        fresh = []
        changed = False
        for item in entries:
            try:
                ts = int(item.get("ts") or 0)
            except Exception:
                ts = 0
            if ts > 0 and (now - ts) <= ttl:
                fresh.append(item)
            else:
                changed = True
        if changed:
            by_chat[key] = fresh
            store["updated_at"] = now
            _save_store_unlocked(store)
        return fresh


__all__ = [
    "find_recent_doc_entry",
    "get_last_resolved_document",
    "list_recent_docs",
    "remember_last_resolved_document",
    "remember_recent_doc",
]
