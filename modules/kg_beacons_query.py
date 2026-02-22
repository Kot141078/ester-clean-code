# -*- coding: utf-8 -*-
"""
modules.kg_beacons_query — fasad po «mayakam».

MOSTY:
- Yavnyy: status(), search(), list_beacons(), beacons_stats().
- Skrytyy #1: ustoychivye otvety bez vneshnikh indeksov.
- Skrytyy #2: odinakovye signatury vo vsekh vyzovakh.

ZEMNOY ABZATs:
Dazhe bez BD mozhno otrisovat spisok/statku i ne padat na importe.

# c=a+b
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

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
            }
        )
    return items, ""


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

def list_beacons(limit: int = 50) -> List[Dict[str, Any]]:
    items, _ = _load_store()
    max_items = max(0, int(limit))
    if items:
        return items[:max_items]
    return [{"id": f"b{i}", "score": 0.0, "label": f"b{i}"} for i in range(max_items)]

def beacons_stats() -> Dict[str, Any]:
    st = status()
    return {"ok": bool(st.get("ok")), "beacons": int(st.get("beacons_count", 0)), "last_error": st.get("last_error", "")}

# c=a+b
