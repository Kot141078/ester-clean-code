# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional

try:
    from modules.memory.user_facts_store import load_user_facts as _load_user_facts  # type: ignore
except Exception:
    _load_user_facts = None  # type: ignore


def _state_root() -> str:
    root = (
        os.environ.get("ESTER_STATE_DIR")
        or os.environ.get("ESTER_HOME")
        or os.environ.get("ESTER_ROOT")
        or os.getcwd()
    ).strip()
    return root


def _profiles_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "profiles")


def _facts_dir() -> str:
    return os.path.join(_state_root(), "data", "memory", "user_facts", "by_user")


def _normalize_user_key(user_id: Any) -> str:
    value = str(user_id or "").strip()
    if not value:
        return ""
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._-")
    return value


def _profile_path(user_id: Any) -> str:
    user_key = _normalize_user_key(user_id)
    if not user_key:
        return ""
    return os.path.join(_profiles_dir(), f"{user_key}.json")


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _merge_unique(items: Iterable[Any], *, limit: int) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        text = _normalize_text(item)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max(1, int(limit)):
            break
    return out


def _load_json(path: str) -> Dict[str, Any]:
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


def _save_json(path: str, payload: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def load_profile_snapshot(user_id: Any) -> Dict[str, Any]:
    return _load_json(_profile_path(user_id))


def _build_summary(display_name: str, facts: List[str]) -> str:
    lead = display_name or "Пользователь"
    if not facts:
        return f"{lead}: устойчивые факты пока не собраны."
    if len(facts) == 1:
        return f"{lead}: {facts[0]}."
    return f"{lead}: {facts[0]}; {facts[1]}."


def refresh_profile_snapshot(
    user_id: Any,
    *,
    display_name: str = "",
    chat_id: Optional[Any] = None,
    user_facts: Optional[List[str]] = None,
    recent_entries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    user_key = _normalize_user_key(user_id)
    if not user_key:
        return {}

    existing = load_profile_snapshot(user_key)
    if user_facts is None and callable(_load_user_facts):
        user_facts = list(_load_user_facts(user_key, include_legacy=False) or [])
    facts = _merge_unique(
        list(user_facts or []) + list(existing.get("facts") or []),
        limit=24,
    )

    aliases = _merge_unique(
        [display_name] + list(existing.get("aliases") or []),
        limit=8,
    )

    recent_fact_preview: List[str] = []
    for row in recent_entries or []:
        if not isinstance(row, dict):
            continue
        text = _normalize_text(row.get("text") or "")
        if not text or text.startswith("["):
            continue
        recent_fact_preview.append(text)
    recent_fact_preview = _merge_unique(recent_fact_preview, limit=6)

    display = _normalize_text(display_name) or _normalize_text(existing.get("display_name") or "")
    if not display and aliases:
        display = aliases[0]

    snapshot = {
        "schema": "ester.user_profile_snapshot.v1",
        "user_id": user_key,
        "display_name": display,
        "aliases": aliases,
        "last_chat_id": str(chat_id) if str(chat_id or "").strip() else str(existing.get("last_chat_id") or ""),
        "facts": facts,
        "recent_fact_preview": recent_fact_preview,
        "summary": _build_summary(display or user_key, facts),
        "updated_ts": int(time.time()),
    }
    ok = _save_json(_profile_path(user_key), snapshot)
    if ok:
        try:
            from modules.memory import memory_index  # type: ignore

            memory_index.ensure_materialized()
        except Exception:
            pass
    return snapshot


def render_profile_context(snapshot: Dict[str, Any]) -> str:
    if not isinstance(snapshot, dict):
        return ""
    lines: List[str] = []
    display = _normalize_text(snapshot.get("display_name") or "")
    if display:
        lines.append(f"- имя: {display}")
    aliases = [str(x).strip() for x in list(snapshot.get("aliases") or []) if str(x).strip()]
    if aliases:
        lines.append(f"- варианты имени: {', '.join(aliases[:4])}")
    facts = [str(x).strip() for x in list(snapshot.get("facts") or []) if str(x).strip()]
    for fact in facts[:6]:
        lines.append(f"- факт: {fact}")
    summary = _normalize_text(snapshot.get("summary") or "")
    if summary:
        lines.append(f"- сводка: {summary}")
    if not lines:
        return ""
    return "[ACTIVE_USER_PROFILE]\n" + "\n".join(lines)


def list_known_user_ids(limit: int = 200) -> List[str]:
    known: List[str] = []
    for root in (_facts_dir(), _profiles_dir()):
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            if not name.endswith(".json"):
                continue
            user_key = _normalize_user_key(name[:-5])
            if not user_key or user_key in known:
                continue
            known.append(user_key)
            if len(known) >= max(1, int(limit)):
                return known
    return known


def refresh_known_profiles(limit: int = 50) -> Dict[str, Any]:
    refreshed: List[str] = []
    for user_key in list_known_user_ids(limit=limit):
        existing = load_profile_snapshot(user_key)
        snapshot = refresh_profile_snapshot(
            user_key,
            display_name=str(existing.get("display_name") or ""),
            chat_id=existing.get("last_chat_id"),
        )
        if snapshot:
            refreshed.append(user_key)
    return {
        "ok": True,
        "count": len(refreshed),
        "user_ids": refreshed,
    }


__all__ = [
    "list_known_user_ids",
    "load_profile_snapshot",
    "refresh_known_profiles",
    "refresh_profile_snapshot",
    "render_profile_context",
]
