# -*- coding: utf-8 -*-
"""
middleware/ingest_guard.py — backpressure/token-bucket dlya /ingest/* s avto-backoff i ban-listom.

Mosty:
- Yavnyy: (Operatsii ↔ Set) spravedlivost ingest po istochnikam (per-source throttle).
- Skrytyy #1: (Infoteoriya ↔ Nablyudaemost) metrika «age v ocheredi», schetchiki hit/deny/backoff.
- Skrytyy #2: (Kibernetika ↔ Ustoychivost) myagkiy rezhim B (log), vysokiy A — zhestkiy.

Zemnoy abzats:
Ne daem odnim istochnikam «zabit trubu»: v sekundu — ne bolshe kvoty, pri oshibkakh zamedlyaem.
# c=a+b
"""
from __future__ import annotations
import os, time, json, re
from typing import Any, Dict, Tuple
from flask import Blueprint, request, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_ingest_guard = Blueprint("ingest_guard", __name__)

AB      = (os.getenv("INGEST_GUARD_AB","A") or "A").upper()
QPS     = float(os.getenv("INGEST_BUCKET_QPS","2.0") or "2.0")
BURST   = int(os.getenv("INGEST_BUCKET_BURST","5") or "5")
B429    = int(os.getenv("INGEST_BACKOFF_429_MS","3000") or "3000")
B5XX    = int(os.getenv("INGEST_BACKOFF_5XX_MS","1500") or "1500")

_STATE: Dict[str, Dict[str, Any]] = {"sources": {}, "hits":0, "denied":0, "backoff":0, "bans": set()}

def _src_key() -> str:
    try:
        if request.is_json:
            src = (request.get_json(silent=True) or {}).get("source","")
        else:
            src = request.args.get("source","")
    except Exception:
        src = ""
    if not src:
        src = request.headers.get("X-Ingest-Source","")
    return src or request.remote_addr or "unknown"

def _bucket(src: str) -> Dict[str,Any]:
    s = _STATE["sources"].setdefault(src, {"tokens": BURST, "ts": time.time(), "backoff_until": 0})
    now = time.time()
    # popolnyaem
    delta = now - s["ts"]
    s["tokens"] = min(BURST, s["tokens"] + delta * QPS)
    s["ts"] = now
    return s

@bp_ingest_guard.before_app_request
def guard():
    path = request.path or ""
    if not re.match(r"^/ingest(/.*)?$", path):
        return None
    if request.method not in ("POST","PUT"):
        return None
    src = _src_key()
    if src in _STATE.get("bans", set()):
        _STATE["denied"] += 1
        if AB=="B": return None
        return jsonify({"ok": False, "error":"banned_source","source": src}), 429
    b = _bucket(src)
    # backoff
    if b["backoff_until"] > time.time():
        _STATE["backoff"] += 1
        if AB=="B": return None
        return jsonify({"ok": False, "error":"backoff","until": b["backoff_until"]}), 429
    # tokens
    if b["tokens"] < 1.0:
        _STATE["denied"] += 1
        if AB=="B": return None
        return jsonify({"ok": False, "error":"rate_limited","qps": QPS, "burst": BURST}), 429
    b["tokens"] -= 1.0
    _STATE["hits"] += 1
    return None

def report_failure(source: str, code: int):
    """Myagkiy API: modul ingest mozhet soobschit ob oshibke, chtoby usilit backoff."""
    b = _bucket(source)
    if code == 429:
        b["backoff_until"] = max(b.get("backoff_until",0), time.time() + B429/1000.0)
    elif 500 <= code < 600:
        b["backoff_until"] = max(b.get("backoff_until",0), time.time() + B5XX/1000.0)

@bp_ingest_guard.route("/ingest/guard/status", methods=["GET"])
def api_status():
    rep = dict(_STATE)
    rep["bans"] = list(_STATE.get("bans", set()))
    return jsonify({"ok": True, "ab": AB, **rep, "qps": QPS, "burst": BURST})

@bp_ingest_guard.route("/ingest/guard/config", methods=["POST"])
def api_config():
    d = request.get_json(silent=True) or {}
    global QPS, BURST
    QPS = float(d.get("qps", QPS))
    BURST = int(d.get("burst", BURST))
    return jsonify({"ok": True, "qps": QPS, "burst": BURST})

@bp_ingest_guard.route("/ingest/guard/ban", methods=["POST"])
def api_ban():
    d = request.get_json(silent=True) or {}
    act = d.get("action","add")
    src = d.get("source","")
    _STATE.setdefault("bans", set())
    if act=="add" and src: _STATE["bans"].add(src)
    if act=="del" and src: _STATE["bans"].discard(src)
    return jsonify({"ok": True, "bans": list(_STATE["bans"])})

def register(app):
    app.register_blueprint(bp_ingest_guard)
# c=a+b