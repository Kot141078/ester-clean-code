# -*- coding: utf-8 -*-
"""routes/coop_missions_routes.py - REST dlya kooperativnykh missiy.

Ruchki:
  POST /coop/bind {"peer":"127.0.0.1:8000"} -> dobavlyaet vedomogo
  POST /coop/start {"mission":"notepad_intro"} -> fiksiruet missiyu
  POST /coop/next {} -> ++index i zapuskaet shag lokalno + u vsekh peers
  GET /coop/status

Lokalnaya chast shaga ispolzuet /missions/step; u peers - /peer/proxy -> /missions/step.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
from typing import Any, Dict
import http.client, json

from modules.thinking.coop_missions import bind as _bind, start as _start, next_step as _next, status as _status
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("coop_missions_routes", __name__, url_prefix="/coop")

def _post_local(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = http.client.HTTPConnection("127.0.0.1", 8000, timeout=10.0)
    conn.request("POST", path, body=json.dumps(payload), headers={"Content-Type":"application/json"})
    r = conn.getresponse()
    t = r.read().decode("utf-8","ignore"); conn.close()
    try: return json.loads(t)
    except Exception: return {"ok": False, "raw": t}

def _post_peer(host: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # use an existing /per/proxy
    return _post_local("/peer/proxy", {"host": host, "path": path, "payload": payload})

@bp.route("/bind", methods=["POST"])
def bind():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(_bind(data.get("peer","").strip()))

@bp.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True, silent=True) or {}
    res = _start(data.get("mission","").strip())
    return jsonify(res)

@bp.route("/next", methods=["POST"])
def next_step():
    st = _status()
    if not st.get("mission"):
        return jsonify({"ok": False, "error": "no_mission"}), 400
    idx = st["index"]
    # lokalno
    loc = _post_local("/missions/step", {"id": st["mission"], "index": idx})
    # peers
    peers = st.get("peers") or []
    peer_res = []
    for p in peers:
        peer_res.append(_post_peer(p, "/missions/step", {"id": st["mission"], "index": idx}))
    _next()
    return jsonify({"ok": True, "index": idx+1, "local": loc, "peers": peer_res})

@bp.route("/status", methods=["GET"])
def status():
    return jsonify(_status())

def register(app):
    app.register_blueprint(bp)
