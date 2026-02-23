# -*- coding: utf-8 -*-
"""
routes/memory_routes.py — UI navigatsiya po pamyati (JSON + Chroma).

Ruchki:
- GET  /memory/list?type=&limit=200
- GET  /memory/search?q=&k=5
- GET  /memory/timeline?days=30&per_day=20&type=&src=auto|json|chroma|hybrid
- GET  /memory/status
- POST /memory/add
- POST /memory/forget
- POST /memory/snapshot
- GET  /memory/admin

ENV:
- MEMORY_UI_BACKEND=auto|json|chroma|hybrid
- MEM_UI_DUAL_WRITE=1|0
- CHROMA_AUTO_HEAL_ENV=1|0     (process-only pointer heal)
- CHROMA_AUTO_HEAL_EAGER=1|0   (init chroma on register)
"""
from __future__ import annotations

import os, time
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, render_template
from modules.memory import store
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory.chroma_adapter import get_chroma_ui  # type: ignore
except Exception:
    get_chroma_ui = None  # type: ignore

bp = Blueprint("memory_routes", __name__, url_prefix="/memory")



def _retention_telemetry() -> dict:
    try:
        mem = list(store._MEM.values())
    except Exception:
        mem = []
    pinned = 0
    decayed = 0
    by_type = {}
    for r in mem:
        try:
            tp = (r.get('type') or r.get('kind') or 'fact').lower()
            by_type[tp] = by_type.get(tp, 0) + 1
            meta = r.get('meta') if isinstance(r.get('meta'), dict) else {}
            if meta.get('pin'):
                pinned += 1
            if 'decay_ts' in meta:
                decayed += 1
        except Exception:
            continue
    return {
        'pinned': pinned,
        'decayed': decayed,
        'by_type': by_type,
    }

def _router_logs(limit: int = 50) -> list:
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    limit = max(1, min(500, limit))
    out = []
    try:
        mem = list(store._MEM.values())
    except Exception:
        mem = []
    for r in mem:
        try:
            meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
            if meta.get("type") != "retrieval_router":
                continue
            out.append(r)
        except Exception:
            continue
    try:
        out.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
    except Exception:
        pass
    return out[:limit]

def _branch_residue(limit: int = 50) -> list:
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    limit = max(1, min(500, limit))
    out = []
    try:
        mem = list(store._MEM.values())
    except Exception:
        mem = []
    for r in mem:
        try:
            meta = r.get("meta") if isinstance(r.get("meta"), dict) else {}
            if meta.get("type") != "branch_residue":
                continue
            out.append(r)
        except Exception:
            continue
    try:
        out.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
    except Exception:
        pass
    return out[:limit]

def _status_payload() -> dict:
    mode = _backend_mode()
    ch_status = None
    if get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if ch is not None:
                ch_status = ch.status()
        except Exception:
            ch_status = None
    rr_metrics = None
    try:
        from modules.rag.retrieval_router import get_metrics  # type: ignore
        rr_metrics = get_metrics()
    except Exception:
        rr_metrics = None
    try:
        br_count = len([r for r in list(store._MEM.values()) if isinstance(r, dict) and (r.get("meta") or {}).get("type") == "branch_residue"])
    except Exception:
        br_count = 0
    return {
        "ok": True,
        "backend": mode,
        "chroma": ch_status,
        "retention": _retention_telemetry(),
        "retrieval_router": rr_metrics,
        "branch_residue_count": br_count,
    }


def _backend_mode() -> str:
    mode = (os.getenv("MEMORY_UI_BACKEND", "auto") or "auto").strip().lower()
    if mode not in ("auto","json","chroma","hybrid"):
        mode = "auto"
    if mode == "json":
        return "json"
    if get_chroma_ui is None:
        return "json"

    try:
        ch = get_chroma_ui()
    except Exception:
        ch = None

    if ch is None or not getattr(ch, "available", lambda: False)():
        return "json"

    # esli auto/hybrid i chroma pustaya — smysla net, ne putaem UI
    try:
        total = int(getattr(ch, "total_count", lambda: 0)() or 0)
    except Exception:
        total = 0
    if mode in ("auto","hybrid") and total <= 0:
        return "json"

    if mode == "chroma":
        return "chroma"
    if mode == "hybrid":
        return "hybrid"
    return "hybrid"

def _dual_write() -> bool:
    v = (os.getenv("MEM_UI_DUAL_WRITE", "1") or "1").strip().lower()
    return v not in ("0","false","no","off")

def _ts_bucket(r: dict, bucket_sec: int = 5) -> int:
    try:
        ts = int(r.get("ts") or r.get("_ts") or 0)
        return ts // bucket_sec
    except Exception:
        return 0

def _dedup_key(r: dict):
    return (str(r.get("type") or ""), (r.get("text") or "").strip(), _ts_bucket(r, 5))

def _dedup(items):
    seen = set()
    out = []
    for r in items:
        key = _dedup_key(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def _maybe_strip_vectors(obj: dict) -> dict:
    keep = (request.args.get("vec","0") or "0").strip().lower() in ("1","true","yes","on")
    if keep:
        return obj
    if not isinstance(obj, dict):
        return obj
    obj = dict(obj)
    for k in ("vec", "vec_legacy", "embedding", "emb", "vector", "vectors"):
        obj.pop(k, None)
    return obj

def _trim(items, limit: int):
    try:
        limit = int(limit)
    except Exception:
        limit = 200
    limit = max(1, limit)
    return (items or [])[:limit]

@bp.route("/status", methods=["GET"])
def status_():
    return jsonify(_status_payload())

@bp.route("/health", methods=["GET"])
def health_():
    return jsonify(_status_payload())

@bp.route("/router_logs", methods=["GET"])
def router_logs_():
    limit = request.args.get("limit", "50")
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 50
    return jsonify({"ok": True, "items": _router_logs(limit_i)})

@bp.route("/branch_residue", methods=["GET"])
def branch_residue_():
    limit = request.args.get("limit", "50")
    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 50
    return jsonify({"ok": True, "items": _branch_residue(limit_i)})

@bp.route("/list", methods=["GET"])
def list_():
    t = request.args.get("type")
    limit = int((request.args.get("limit","200") or "200").strip() or 200)
    limit = max(1, min(1000, limit))
    mode = _backend_mode()

    items = []
    lim_src = limit if mode != "hybrid" else min(2000, max(200, limit * 3))

    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                for r in ch.list_recent(type_filter=t, limit=lim_src):
                    rr = dict(r); rr["_src"]="chroma"
                    rr = _maybe_strip_vectors(rr)
                    items.append(rr)
        except Exception:
            pass

    if mode in ("json","hybrid"):
        try:
            data = [r for r in store._MEM.values() if (not t or r.get("type") == t)]
            data.sort(key=lambda x: int(x.get("ts",0) or 0), reverse=True)
            data = data[:lim_src]
            for r in data:
                rr = dict(r); rr["_src"]="json"
                rr = _maybe_strip_vectors(rr)
                items.append(rr)
        except Exception:
            pass

    if mode == "hybrid":
        items = _dedup(items)
        items = _trim(items, limit)
    else:
        items = _trim(items, limit)

    return jsonify({"ok": True, "backend": mode, "count": len(items), "items": items})

@bp.route("/search", methods=["GET"])
def search_():
    q = (request.args.get("q","") or "").strip()
    k = int((request.args.get("k","5") or "5").strip() or 5)
    k = max(1, min(20, k))
    mode = _backend_mode()
    results = []

    k_src = k if mode != "hybrid" else min(50, max(10, k * 3))

    if q and mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                for r in ch.search(q, top_k=k_src):
                    rr = dict(r); rr["_src"]="chroma"
                    rr = _maybe_strip_vectors(rr)
                    results.append(rr)
        except Exception:
            pass

    if q and mode in ("json","hybrid"):
        try:
            for r in store.query(q, top_k=k_src):
                rr = dict(r); rr["_src"]="json"
                rr = _maybe_strip_vectors(rr)
                results.append(rr)
        except Exception:
            pass

    if mode == "hybrid":
        results = _dedup(results)
        results = _trim(results, k)
    else:
        results = _trim(results, k)

    return jsonify({"ok": True, "backend": mode, "query": q, "k": k, "results": results})

@bp.route("/timeline", methods=["GET"])
def timeline_():
    days = int((request.args.get("days","30") or "30").strip() or 30)
    per_day = int((request.args.get("per_day","20") or "20").strip() or 20)
    t = request.args.get("type")
    src = (request.args.get("src","auto") or "auto").strip().lower()
    if src not in ("auto","json","chroma","hybrid"):
        src = "auto"

    mode = _backend_mode()
    if src != "auto":
        mode = src

    days = max(1, min(365, days))
    per_day = max(1, min(200, per_day))
    now = int(time.time())
    cutoff = now - days * 86400

    buckets = {}
    seen_per_day = {}

    def put(day: str, rec: dict):
        arr = buckets.get(day)
        if arr is None:
            arr = []
            buckets[day] = arr
        s = seen_per_day.get(day)
        if s is None:
            s = set()
            seen_per_day[day] = s

        key = _dedup_key(rec)
        if key in s:
            return
        s.add(key)

        if len(arr) < per_day:
            arr.append(rec)

    if mode in ("json","hybrid"):
        try:
            for r in store._MEM.values():
                if t and r.get("type") != t:
                    continue
                ts = int(r.get("ts") or 0)
                if ts < cutoff:
                    continue
                day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                rr = dict(r); rr["_src"]="json"; rr["_ts"]=ts
                rr = _maybe_strip_vectors(rr)
                put(day, rr)
        except Exception:
            pass

    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                lim = min(5000, max(500, days * per_day * 3))
                for r in ch.list_recent(type_filter=t, limit=lim):
                    ts = r.get("ts")
                    if ts is None:
                        continue
                    try:
                        ts = int(ts)
                    except Exception:
                        continue
                    if ts < cutoff:
                        continue
                    day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    rr = dict(r); rr["_src"]="chroma"; rr["_ts"]=ts
                    rr = _maybe_strip_vectors(rr)
                    put(day, rr)
        except Exception:
            pass

    days_sorted = sorted(buckets.keys(), reverse=True)
    out = []
    for d in days_sorted:
        arr = buckets[d]
        try:
            arr.sort(key=lambda x: int(x.get("_ts") or 0), reverse=True)
        except Exception:
            pass
        out.append({"day": d, "count": len(arr), "items": arr[:per_day]})

    return jsonify({"ok": True, "backend": mode, "days": days, "per_day": per_day, "type": t, "buckets": out})

@bp.route("/add", methods=["POST"])
def add_():
    d = request.get_json(force=True, silent=True) or {}
    typ = d.get("type","fact")
    txt = d.get("text","")
    meta = d.get("meta")
    mode = _backend_mode()
    dual = _dual_write()

    rec_json = None
    rec_chroma = None

    try:
        rec_json = memory_add(typ, txt, meta)
    except Exception:
        rec_json = None

    if mode in ("chroma","hybrid") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                if dual or mode == "chroma":
                    rec_chroma = ch.add_record(typ, txt, meta)
        except Exception:
            rec_chroma = None

    return jsonify({"ok": True, "backend": mode, "dual_write": dual, "record": {"json": rec_json, "chroma": rec_chroma}})

@bp.route("/forget", methods=["POST"])
def forget_():
    d = request.get_json(force=True, silent=True) or {}
    rid = (d.get("id","") or "").strip()
    src = (d.get("src","both") or "both").strip().lower()
    if src not in ("json","chroma","both"):
        src = "both"

    ok_json = False
    ok_chroma = False

    if rid and src in ("json","both"):
        try: ok_json = bool(store.forget(rid))
        except Exception: ok_json = False

    if rid and src in ("chroma","both") and get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if (not ESTER_MEM_FACADE) and ch is not None and ch.available():
                ok_chroma = bool(ch.delete(rid))
        except Exception:
            ok_chroma = False

    return jsonify({"ok": bool(ok_json or ok_chroma), "json": ok_json, "chroma": ok_chroma})

@bp.route("/snapshot", methods=["POST"])
def snapshot_():
    path = None
    try:
        store.snapshot()
        path = getattr(store, "_FILE", None)
    except Exception:
        pass

    chroma_status = None
    if get_chroma_ui is not None:
        try:
            ch = get_chroma_ui()
            if ch is not None:
                chroma_status = ch.status()
        except Exception:
            chroma_status = None

    return jsonify({"ok": True, "json_path": path, "chroma": chroma_status})

@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_memory.html")

def register(app):
    app.register_blueprint(bp)
    # eager init: so auto-heal env happens early (process-only, safe)
    eager = (os.getenv("CHROMA_AUTO_HEAL_EAGER","1") or "1").strip().lower() in ("1","true","yes","on")
    if eager and get_chroma_ui is not None:
        try:
            get_chroma_ui()
        except Exception:
            pass
