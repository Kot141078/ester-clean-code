# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime
import json
import os
import re
import threading
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


def _facts_root() -> str:
    return os.path.join(_state_root(), "data", "memory", "user_facts", "by_user")


def _legacy_path() -> str:
    return os.path.join(_state_root(), "data", "user_facts.json")


def _normalize_fact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_user_key(user_id: Any) -> str:
    value = str(user_id or "").strip()
    if not value:
        return ""
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return value


def _facts_path(user_id: Any) -> str:
    user_key = _normalize_user_key(user_id)
    if not user_key:
        return ""
    return os.path.join(_facts_root(), f"{user_key}.json")


def _facts_payload(facts: List[str], *, user_key: str = "", history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    return {
        "user_id": user_key,
        "facts": list(facts or []),
        "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        "history": list(history or []),
    }


def _load_payload(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _extract_facts(data: Dict[str, Any]) -> List[str]:
    raw = data.get("facts") if isinstance(data, dict) else []
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    seen = set()
    for item in raw:
        fact = _normalize_fact(item)
        if not fact:
            continue
        key = fact.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(fact)
    return out


def _write_payload(path: str, payload: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def load_user_facts(
    user_id: Any,
    *,
    include_legacy: bool = False,
    legacy_path: Optional[str] = None,
) -> List[str]:
    user_path = _facts_path(user_id)
    legacy_file = str(legacy_path or _legacy_path()).strip()
    with _LOCK:
        facts = _extract_facts(_load_payload(user_path))
        if include_legacy and legacy_file:
            legacy_facts = _extract_facts(_load_payload(legacy_file))
            if legacy_facts:
                seen = {fact.casefold() for fact in facts}
                for fact in legacy_facts:
                    key = fact.casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    facts.append(fact)
        return facts


def save_user_facts(
    user_id: Any,
    facts: List[str],
    *,
    sync_legacy: bool = False,
    legacy_path: Optional[str] = None,
) -> bool:
    normalized: List[str] = []
    seen = set()
    for item in facts or []:
        fact = _normalize_fact(item)
        if not fact:
            continue
        key = fact.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(fact)

    user_key = _normalize_user_key(user_id)
    user_path = _facts_path(user_id)
    legacy_file = str(legacy_path or _legacy_path()).strip()

    with _LOCK:
        ok = True
        if user_path:
            current = _load_payload(user_path)
            history = list(current.get("history") or []) if isinstance(current, dict) else []
            history.append(
                {
                    "ts": int(datetime.datetime.now().timestamp()),
                    "facts_count": len(normalized),
                }
            )
            history = history[-64:]
            ok = _write_payload(user_path, _facts_payload(normalized, user_key=user_key, history=history))
        if sync_legacy and legacy_file:
            ok = _write_payload(legacy_file, _facts_payload(normalized)) and ok
        if ok:
            try:
                from modules.memory import memory_index  # type: ignore

                memory_index.ensure_materialized()
            except Exception:
                pass
        return ok


__all__ = [
    "load_user_facts",
    "save_user_facts",
]
