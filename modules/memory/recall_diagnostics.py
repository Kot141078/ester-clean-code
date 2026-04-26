# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _diag_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "diagnostics", "recall")


def _trim_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _append_jsonl(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _block_preview(bundle: Dict[str, Any], key: str, max_chars: int = 360) -> str:
    return _trim_text(bundle.get(key) or "", max_chars)


def record_active_bundle(
    *,
    query: str,
    user_id: Any,
    chat_id: Any,
    bundle: Dict[str, Any],
    profile_snapshot: Optional[Dict[str, Any]] = None,
    provenance: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    ts = int(time.time())
    stats = dict(bundle.get("stats") or {})
    provenance_list = [dict(item) for item in (provenance or []) if isinstance(item, dict)]
    payload = {
        "schema": "ester.recall.diagnostic.v1",
        "ts": ts,
        "user_id": str(user_id or "").strip(),
        "chat_id": str(chat_id or "").strip(),
        "query": _trim_text(query, 500),
        "bundle_schema": str(bundle.get("schema") or ""),
        "stats": stats,
        "sections": {
            "profile": _block_preview(bundle, "profile_block"),
            "honesty": _block_preview(bundle, "honesty_block", max_chars=300),
            "facts": _block_preview(bundle, "facts_block"),
            "recent_facts": _block_preview(bundle, "recent_facts_block"),
            "recent_doc": _block_preview(bundle, "recent_doc_block"),
            "retrieval": _block_preview(bundle, "retrieval_block", max_chars=500),
            "memory_stance": _block_preview(bundle, "memory_stance", max_chars=240),
        },
        "profile_summary": _trim_text((profile_snapshot or {}).get("summary") or "", 280),
        "provenance_count": len(provenance_list),
        "provenance_preview": [
            {
                "doc_id": str(item.get("doc_id") or ""),
                "path": _trim_text(item.get("path") or "", 180),
                "page": item.get("page"),
                "offset": item.get("offset"),
            }
            for item in provenance_list[:6]
        ],
    }

    base = _diag_dir()
    stem = time.strftime("%Y%m%d_%H%M%S", time.localtime(ts))
    json_path = os.path.join(base, f"active_bundle_{stem}.json")
    latest_path = os.path.join(base, "latest.json")
    history_path = os.path.join(base, "history.jsonl")
    _write_json(json_path, payload)
    _write_json(latest_path, payload)
    _append_jsonl(history_path, payload)
    try:
        from modules.memory import memory_index  # type: ignore

        memory_index.ensure_materialized()
    except Exception:
        pass
    return {"ok": True, "path": json_path, "latest_path": latest_path, "history_path": history_path, "report": payload}


def latest() -> Dict[str, Any]:
    path = os.path.join(_diag_dir(), "latest.json")
    if not os.path.exists(path):
        return {"ok": False, "error": "not_found"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            return {"ok": True, "report": data}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": False, "error": "bad_payload"}


__all__ = [
    "latest",
    "record_active_bundle",
]
