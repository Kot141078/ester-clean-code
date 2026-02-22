# -*- coding: utf-8 -*-
from __future__ import annotations
import os, time, traceback
from typing import Any, Dict, Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from modules.memory import store as _mem_store  # type: ignore
except Exception:
    _mem_store = None  # type: ignore
try:
    from modules.memory import qa as _mem_qa  # type: ignore
except Exception:
    _mem_qa = None  # type: ignore
try:
    from modules.memory import events as _mem_events  # type: ignore
except Exception:
    _mem_events = None  # type: ignore

_ROLLBACK = False

def _mode() -> str:
    if _ROLLBACK:
        return "A"
    return os.getenv("ESTER_MEMORY_FLOW_AB", "A").strip().upper() or "A"

def is_enabled() -> bool:
    return _mode() in ("B", "AB", "ON")

def _rollback(reason: str) -> None:
    global _ROLLBACK
    _ROLLBACK = True
    try:
        print(f"[memory_flow] rollback to A due to: {reason}")
    except Exception:
        pass

def _is_interesting_text(text: Optional[str]) -> bool:
    if not text:
        return False
    stripped = text.strip()
    try:
        min_len = int(os.getenv("ESTER_MEMORY_FLOW_MIN_LEN", "40"))
    except Exception:
        min_len = 40
    if len(stripped) < max(1, min_len):
        return False
    return True

def safe_recall(query: str, limit: int = 5) -> Dict[str, Any]:
    if not is_enabled():
        return {"ok": False, "reason": "disabled", "items": []}
    q = (query or "").strip()
    if not q:
        return {"ok": False, "reason": "empty_query", "items": []}
    try:
        limit_env = int(os.getenv("ESTER_MEMORY_FLOW_MAX_ITEMS", "5"))
        limit_eff = max(1, min(limit_env, 32))
    except Exception:
        limit_eff = 5

    try:
        if _mem_qa is not None and hasattr(_mem_qa, "search"):
            res = _mem_qa.search(q, limit=limit_eff)  # type: ignore[arg-type]
            if isinstance(res, dict) and "items" in res:
                items = res.get("items") or []
            else:
                items = res or []
            return {"ok": True, "src": "qa", "items": items}
    except Exception:
        pass

    try:
        if _mem_store is not None and hasattr(_mem_store, "search"):
            items = _mem_store.search(q, limit=limit_eff)  # type: ignore[arg-type]
            return {"ok": True, "src": "store.search", "items": items or []}
    except Exception:
        pass

    return {"ok": False, "reason": "no_backend", "items": []}

def record_dialog(prompt: Optional[str], reply: Optional[str], meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not is_enabled():
        return {"ok": False, "reason": "disabled"}
    if not (_is_interesting_text(prompt) or _is_interesting_text(reply)):
        return {"ok": False, "reason": "not_interesting"}
    meta = dict(meta or {})
    meta.setdefault("ts", time.time())
    meta.setdefault("kind", "dialog")
    meta.setdefault("source", "memory_flow")
    meta.setdefault("c", "a+b")
    try:
        payload = {
            "prompt": (prompt or "").strip(),
            "reply": (reply or "").strip(),
        }
        if _mem_events is not None and hasattr(_mem_events, "record_event"):
            ev = {"type": "ester_dialog", "payload": payload, "meta": meta}
            _mem_events.record_event(ev)  # type: ignore[arg-type]
            return {"ok": True, "via": "events"}
    except Exception:
        pass
    try:
        if _mem_store is not None and hasattr(_mem_store, "add_record"):
            rec = {
                "type": "dialog",
                "text": f"Q: {payload['prompt']}\nA: {payload['reply']}",
                "meta": meta,
            }
            memory_add(rec)  # type: ignore[arg-type]
            return {"ok": True, "via": "store"}
    except Exception as e:
        tb = traceback.format_exc()
        _rollback(f"record_dialog_error:{e!r}")
        try:
            print("[memory_flow] record_dialog_error", tb)
        except Exception:
            pass
        return {"ok": False, "reason": "exception"}
    return {"ok": False, "reason": "no_backend"}

__all__ = ["is_enabled", "safe_recall", "record_dialog"]