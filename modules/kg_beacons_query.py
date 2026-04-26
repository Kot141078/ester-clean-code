# -*- coding: utf-8 -*-
"""
modules.kg_beacons_query — фасад по «маякам».

МОСТЫ:
- Явный: status(), search(), list_beacons(), beacons_stats().
- Скрытый #1: устойчивые ответы без внешних индексов.
- Скрытый #2: одинаковые сигнатуры во всех вызовах.

ЗЕМНОЙ АБЗАЦ:
Даже без БД можно отрисовать список/статку и не падать на импорте.

# c=a+b
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

BEACONS_DB = os.getenv("KG_BEACONS_DB", "data/kg/beacons.json").strip() or "data/kg/beacons.json"


def _store_path() -> Path:
    return Path(BEACONS_DB).resolve()


def _load_store() -> Tuple[List[Dict[str, Any]], str]:
    p = _store_path()
    if not p.exists():
        return [], "store_missing"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return [], f"store_read_error:{e.__class__.__name__}"
    items: List[Dict[str, Any]] = []
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict):
        rows = raw.get("beacons") or raw.get("items") or []
    else:
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or row.get("name") or "").strip()
        if not rid:
            continue
        items.append(
            {
                "id": rid,
                "score": float(row.get("score") or 0.0),
                "label": str(row.get("label") or row.get("name") or rid),
                **_optional_beacon_fields(row),
            }
        )
    return items, ""


def _optional_beacon_fields(row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    kind = str(row.get("kind") or row.get("type") or row.get("event") or "").strip()
    if kind:
        out["kind"] = kind
    ts = _coerce_ts(
        row.get("ts")
        or row.get("timestamp")
        or row.get("created_ts")
        or row.get("created_at")
        or row.get("time")
    )
    if ts is not None:
        out["ts"] = ts
    return out


def _coerce_ts(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _kind_set(kinds: Iterable[str] | None) -> set[str]:
    return {str(kind).strip() for kind in (kinds or []) if str(kind).strip()}


def _filter_items(
    items: List[Dict[str, Any]],
    *,
    since: float | None = None,
    kinds: Iterable[str] | None = None,
) -> List[Dict[str, Any]]:
    kind_filter = _kind_set(kinds)
    out: List[Dict[str, Any]] = []
    for item in items:
        if since is not None:
            ts = _coerce_ts(item.get("ts"))
            if ts is None or ts < float(since):
                continue
        if kind_filter and str(item.get("kind") or "").strip() not in kind_filter:
            continue
        out.append(item)
    return out


def status() -> Dict[str, Any]:
    enabled = (os.getenv("KG_BEACONS_ENABLED", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}
    p = _store_path()
    items, err = _load_store()
    return {
        "ok": bool(enabled and not err),
        "beacons_enabled": bool(enabled),
        "store_path": str(p),
        "beacons_count": int(len(items)),
        "last_update_ts": int(p.stat().st_mtime) if p.exists() else 0,
        "last_error": str(err),
    }

def search(query: str = "", limit: int = 10) -> Dict[str, Any]:
    q = str(query or "").strip().lower()
    max_items = max(1, int(limit))
    items, err = _load_store()
    if err:
        out: List[Dict[str, Any]] = []
        if q:
            out.append({"id": "echo", "score": 0.0, "label": q})
        return {"ok": False, "items": out[:max_items], "error": err}

    if not q:
        return {"ok": True, "items": items[:max_items]}
    scored = []
    for it in items:
        text = f"{it.get('id','')} {it.get('label','')}".lower()
        score = 1.0 if q in text else 0.0
        if score > 0.0:
            scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    return {"ok": True, "items": [it for _, it in scored[:max_items]]}

def list_beacons(
    limit: int = 50,
    since: float | None = None,
    kinds: Iterable[str] | None = None,
) -> List[Dict[str, Any]]:
    items, _ = _load_store()
    max_items = max(0, int(limit))
    items = _filter_items(items, since=since, kinds=kinds)
    if items:
        return items[:max_items]
    if since is not None or _kind_set(kinds):
        return []
    return [{"id": f"b{i}", "score": 0.0, "label": f"b{i}"} for i in range(max_items)]

def beacons_stats(
    limit: int = 1000,
    since: float | None = None,
    kinds: Iterable[str] | None = None,
) -> Dict[str, Any]:
    st = status()
    rows = list_beacons(limit=limit, since=since, kinds=kinds)
    return {
        "ok": bool(st.get("ok")),
        "beacons": len(rows),
        "stored_beacons": int(st.get("beacons_count", 0)),
        "limit": max(0, int(limit)),
        "since": since,
        "kinds": sorted(_kind_set(kinds)),
        "last_error": st.get("last_error", ""),
    }

# c=a+b
