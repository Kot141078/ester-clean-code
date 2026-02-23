# -*- coding: utf-8 -*-
"""
routes/ingest_proxy_routes.py - proksi dlya /ingest/submit s backpressure i bekoffom.

Mosty:
- Yavnyy: (Ingest ↔ Kvoty) reguliruem potoki per-source.
- Skrytyy #1: (Nadezhnost ↔ Bekoff) avtomaticheski zamedlyaem problemnye istochniki.
- Skrytyy #2: (Sovmestimost ↔ Proksirovanie) kontrakt /ingest/submit neizmenen - my lish obertka.

Zemnoy abzats:
Kak «umnaya priemnaya»: prinimaet pachku, vydaet talonchik i otpravlyaet dalshe, no bez ocheredey-v-khaos.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import json, time
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("ingest_proxy_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.ingest.backpressure import allow as _allow, record_result as _rec, set_queue_age as _qage  # type: ignore
except Exception:
    _allow=lambda s,w: {"allow": True}  # type: ignore
    _rec=lambda s,ok,code=None: None  # type: ignore
    _qage=lambda k,ts: None  # type: ignore

def _http_post(path: str, obj: dict)->dict:
    import urllib.request
    data=json.dumps(obj).encode("utf-8")
    req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

@bp.route("/ingest/submit_proxy", methods=["POST"])
def api_ingest_submit_proxy():
    d=request.get_json(True, True) or {}
    source=str(d.get("source","unknown"))
    payload=d.get("payload") or {}
    weight=float(d.get("weight",1.0) or 1.0)
    gate=_allow(source, weight)
    if not gate.get("allow", True):
        return jsonify({"ok": False, "error":"rate_limited", "gate": gate}), 429
    # fiksiruem «vozrast» dlya monitoringa
    tid=f"I{int(time.time())}"
    _qage(tid, int(time.time()))
    try:
        rep=_http_post("/ingest/submit", payload)
        _rec(source, bool(rep.get("ok",False)), None)
        rep["proxy_tid"]=tid
        return jsonify(rep)
    except Exception as e:
        _rec(source, False, 500)
        return jsonify({"ok": False, "error": str(e), "proxy_tid": tid}), 502
# c=a+b