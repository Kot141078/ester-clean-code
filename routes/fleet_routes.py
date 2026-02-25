# -*- coding: utf-8 -*-
"""routes/fleet_routes.py - REST: fleet sister (uzly, zadachi, naznachenie, vorker).

Mosty:
- Yavnyy: (Veb ↔ Raspredelenie) edinye tochki dlya registratsii, ocheredi i otchetov.
- Skrytyy #1: (Ostorozhnost ↔ Pilyuli/HMAC) submit pod pilyuley; worker-vyzovy i register mozhno prikryt HMAC.
- Skrytyy #2: (Avtonomiya ↔ Volya) est eksheny dlya planirovschika i garazha.

Zemnoy abzats:
Dispetcherskaya: syuda “zvonyat” mashiny, otsyuda im dayut rabotu, syuda zhe prikhodyat otchety.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import json, hmac, hashlib, os
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("fleet_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.fleet.core import register_node as _reg, heartbeat as _hb, submit_task as _submit, status as _status, assign_tick as _assign, worker_pull as _pull, worker_report as _report  # type: ignore
    from modules.fleet.worker import tick as _worker_tick  # type: ignore
except Exception:
    _reg=_hb=_submit=_status=_assign=_pull=_report=_worker_tick=None  # type: ignore

SHARED_KEY = (os.getenv("FLEET_SHARED_KEY","") or "").encode("utf-8")

def _pill_ok(req, pattern:str, method:str)->bool:
    tok=req.args.get("pill","")
    if not tok: return False
    try:
        from modules.caution.pill import verify  # type: ignore
        rep=verify(tok, pattern=pattern, method=method)
        return bool(rep.get("ok", False))
    except Exception:
        return True if tok else False

def _hmac_ok(raw: str, req)->bool:
    if not SHARED_KEY: return True
    got=req.headers.get("X-Fleet-Sign","")
    try:
        mac=hmac.new(SHARED_KEY, raw.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, got)
    except Exception:
        return False

@bp.route("/fleet/node/register", methods=["POST"])
def api_reg():
    if _reg is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    raw=request.get_data(as_text=True)
    if not _hmac_ok(raw, request): return jsonify({"ok": False, "error":"hmac_required"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_reg(str(d.get("node_id","")), str(d.get("url","")), d.get("capacity") or {}, list(d.get("tags") or [])))

@bp.route("/fleet/node/heartbeat", methods=["POST"])
def api_hb():
    if _hb is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_hb(str(d.get("node_id","")), d.get("load") or {}))

@bp.route("/fleet/task/submit", methods=["POST"])
def api_submit():
    if _submit is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    if not _pill_ok(request, "^/fleet/task/submit$", "POST"): return jsonify({"ok": False, "error":"pill_required"}), 403
    d=request.get_json(True, True) or {}
    return jsonify(_submit(d.get("spec") or {}))

@bp.route("/fleet/task/status", methods=["GET"])
def api_status():
    if _status is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    tid=str(request.args.get("id",""))
    return jsonify(_status(tid))

@bp.route("/fleet/assign/tick", methods=["POST"])
def api_assign():
    if _assign is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    return jsonify(_assign())

@bp.route("/fleet/worker/pull", methods=["POST"])
def api_pull():
    if _pull is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    d=request.get_json(True, True) or {}
    items=_pull(str(d.get("node_id","")))
    return jsonify({"ok": True, "items": items})

@bp.route("/fleet/worker/report", methods=["POST"])
def api_report():
    if _report is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_report(str(d.get("node_id","")), str(d.get("id","")), bool(d.get("ok",False)), d.get("result") or {}))

@bp.route("/fleet/worker/tick", methods=["POST"])
def api_worker_tick():
    if _worker_tick is None: return jsonify({"ok": False, "error":"fleet_unavailable"}), 500
    return jsonify(_worker_tick())
# c=a+b