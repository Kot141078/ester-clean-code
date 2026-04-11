# -*- coding: utf-8 -*-
"""
Memory Facade: canonical entrypoint for memory writes.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Optional

ESTER_MEM_FACADE = (os.getenv("ESTER_MEM_FACADE", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
ESTER_MEM_FACADE_STRICT = (os.getenv("ESTER_MEM_FACADE_STRICT", "0") or "0").strip().lower() in ("1", "true", "yes", "on")
ESTER_RETENTION_V2 = (os.getenv("ESTER_RETENTION_V2", "1") or "1").strip().lower() not in ("0", "false", "no", "off")
ESTER_MEMORY_META_DEFAULTS = (os.getenv("ESTER_MEMORY_META_DEFAULTS", "0") or "0").strip().lower() in ("1", "true", "yes", "on")


_tls = threading.local()


def _set_in_facade(val: bool) -> None:
    _tls.in_facade = bool(val)


def in_facade() -> bool:
    return bool(getattr(_tls, "in_facade", False))


def _violations_path() -> str:
    return os.path.join("data", "memory", "mem_facade_violations.jsonl")


def log_violation(kind: str, text: str, meta: Optional[Dict[str, Any]] = None, source: str = "") -> None:
    try:
        os.makedirs(os.path.dirname(_violations_path()), exist_ok=True)
        rec = {
            "ts": int(time.time()),
            "kind": kind,
            "text_preview": (text or "")[:240],
            "meta": meta or {},
            "source": source,
        }
        with open(_violations_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass




def _normalize_kind(kind: str) -> str:
    k = (kind or '').strip().lower()
    # Normalize common aliases
    if k in ('chat', 'conversation'):
        return 'dialog'
    if k in ('doc_summary', 'docsummary', 'summary_doc'):
        return 'doc_summary'
    return k or 'fact'


def memory_add(kind: str, text: str, meta: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Canonical memory entrypoint.
    Routes to structured store / vstore / chroma in one place.
    """
    if not text:
        return
    meta = meta or {}
    k = _normalize_kind(kind)
    if ESTER_RETENTION_V2 and k in {"doc", "doc_summary", "fact"}:
        meta.setdefault("pin", True)
    if ESTER_MEMORY_META_DEFAULTS:
        from modules.memory.kind_registry import kind_spec  # type: ignore
        src = meta.get("source")
        meta.setdefault("source", src or "unknown")
        meta.setdefault("origin", src or "system")
        spec = kind_spec(k)
        meta.setdefault("layer", spec.layer if spec else "unknown")
    _set_in_facade(True)
    rec = None
    try:
        from modules.memory import store  # type: ignore
        rec = store.add_record(k, text, meta=meta)  # type: ignore[attr-defined]

        try:
            from modules.memory.core_sqlite import core_enabled, dual_write_enabled, write_memory_add  # type: ignore

            if core_enabled() and dual_write_enabled():
                write_memory_add(k, text, meta=meta, legacy_record=rec)
        except Exception:
            pass

        try:
            from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                ch.add_record(k, text, meta or {})
        except Exception:
            pass
    finally:
        _set_in_facade(False)
    return rec


__all__ = ["memory_add", "ESTER_MEM_FACADE", "ESTER_MEM_FACADE_STRICT", "log_violation", "in_facade"]
