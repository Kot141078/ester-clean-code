# -*- coding: utf-8 -*-
"""
routes_trace.py — blyuprint trassirovki.
Endpointy:
  GET /trace/recent?limit=... -> { ok, items: [...] }
  GET /trace/item?id=...      -> { ok, item } | 404
Chitaet JSONL-logi iz kataloga TRACE_LOG_DIR (po umolchaniyu vstore/logs).
Graceful fallback: esli trace_logger.TraceLogger nedostupen/nepolon, chitaem fayly napryamuyu.
Nikakikh blokirovok osnovnogo potoka: prostoe chtenie, bez isklyucheniy naruzhu.
"""
from __future__ import annotations

import glob
import json
import os
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Put k logam (bez zavisimosti ot config.py dlya sovmestimosti so starymi sborkami)
_LOG_DIR = os.getenv("TRACE_LOG_DIR", "vstore/logs")
os.makedirs(_LOG_DIR, exist_ok=True)

# Pytaemsya ispolzovat suschestvuyuschiy TraceLogger, no ne zavyazyvaemsya na nego zhestko.
_TraceLogger = None
try:
    from trace_logger import TraceLogger as _TraceLogger  # type: ignore
except Exception:
    _TraceLogger = None

trace_blueprint = Blueprint("trace", __name__, url_prefix="/trace")


def _list_log_files() -> List[str]:
    # Podderzhivaem formaty: YYYY-MM-DD.jsonl i trace_YYYY-MM-DD.jsonl
    patt1 = os.path.join(_LOG_DIR, "*.jsonl")
    patt2 = os.path.join(_LOG_DIR, "trace_*.jsonl")
    files = set(glob.glob(patt1)) | set(glob.glob(patt2))
    return sorted(files, key=lambda p: os.path.getmtime(p), reverse=True)


def _tail_file(path: str, limit: int) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines = lines[-limit:] if limit > 0 else lines
        out: List[Dict[str, Any]] = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _recent_fallback(limit: int) -> List[Dict[str, Any]]:
    """Sobiraem zapisi iz neskolkikh poslednikh faylov, poka ne naberem limit."""
    items: List[Dict[str, Any]] = []
    for fp in _list_log_files():
        need = max(0, limit - len(items))
        if need <= 0:
            break
        chunk = _tail_file(fp, need)
        # starye — snizu, no my idem po faylam nazad; normalizuem poryadok po ts/timestamp
        items.extend(chunk)

    # Sortirovka po vremeni, esli est ts|timestamp
    def _key(x: Dict[str, Any]):
        return x.get("ts") or x.get("timestamp") or 0

    items.sort(key=_key, reverse=True)
    return items[:limit]


def _find_item_fallback(event_id: str) -> Optional[Dict[str, Any]]:
    for fp in _list_log_files():
        try:
            with open(fp, "r", encoding="utf-8") as f:
                for ln in f:
                    try:
                        obj = json.loads(ln.strip())
                    except Exception:
                        continue
                    if obj.get("event_id") == event_id:
                        return obj
        except Exception:
            continue
    return None


@trace_blueprint.get("/recent")
def get_recent():
    try:
        limit = int(request.args.get("limit", 20))
    except Exception:
        limit = 20

    items: List[Dict[str, Any]] = []
    # Esli est TraceLogger s get_recent — ispolzuem
    if _TraceLogger is not None:
        try:
            logger = _TraceLogger(_LOG_DIR)
            # Popytka poluchit srazu mnozhestvo zapisey (esli realizatsiya podderzhivaet tolko "segodnya" — dopolnim fallback'om)
            today_items = logger.get_recent(limit)  # type: ignore[attr-defined]
            items = today_items or []
            if len(items) < limit:
                # dobiraem iz proshlykh dney
                extra = _recent_fallback(limit)
                # merdzh po event_id, bez dubley:
                seen = {i.get("event_id") for i in items if "event_id" in i}
                for it in extra:
                    eid = it.get("event_id")
                    if not eid or eid not in seen:
                        items.append(it)
                        seen.add(eid)
                # finalnaya normalizatsiya poryadka
                items = sorted(
                    items,
                    key=lambda x: x.get("ts") or x.get("timestamp") or 0,
                    reverse=True,
                )[:limit]
        except Exception:
            items = _recent_fallback(limit)
    else:
        items = _recent_fallback(limit)

    return jsonify({"ok": True, "items": items})


@trace_blueprint.get("/item")
def get_item():
    event_id = request.args.get("id", "").strip()
    if not event_id:
        return jsonify({"ok": False, "error": "Missing 'id'"}), 400

    obj: Optional[Dict[str, Any]] = None
    if _TraceLogger is not None:
        try:
            logger = _TraceLogger(_LOG_DIR)
            obj = logger.get_item(event_id)  # type: ignore[attr-defined]
        except Exception:
            obj = None
    if obj is None:
        obj = _find_item_fallback(event_id)

    if obj is None:
        return jsonify({"ok": False, "error": "Not found"}), 404
# return jsonify({"ok": True, "item": obj})