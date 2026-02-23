# -*- coding: utf-8 -*-
"""
routes/actions_workbench_ab_routes.py - eksheny «voli» dlya Workbench i A/B.

Mosty:
- Yavnyy: (Mysli ↔ Instrumenty) mozg sozdaet fayly, pishet kod, rulit A/B.
- Skrytyy #1: (RBAC ↔ Ostorozhnost) vse idet cherez REST i roli.
- Skrytyy #2: (AutoDiscover ↔ Zhiznennyy tsikl) posle scaffold mozhno srazu registrirovat.

Zemnoy abzats:
Odni korotkie komandy - i u Ester est «payalnik» (Workbench) i «tumbler» (A/B) pod rukoy.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify, request

bp = Blueprint("actions_workbench_ab_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.thinking.action_registry import register as _areg  # type: ignore
except Exception:
    _areg=None  # type: ignore

import json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _post(path: str, payload: dict, timeout: int=60):
    data=json.dumps(payload or {}).encode("utf-8")
    req=urllib.request.Request("http://127.0.0.1:8000"+path, data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        import json as _j; return _j.loads(r.read().decode("utf-8"))

def _get(path: str, timeout: int=20):
    import urllib.request, json as _j
    with urllib.request.urlopen("http://127.0.0.1:8000"+path, timeout=timeout) as r:
        return _j.loads(r.read().decode("utf-8"))

def _reg():
    if _areg is None: return
    _areg("workbench.scaffold", {"kind":"str","package":"str","name":"str"}, {"ok":"bool"}, 2,
          lambda a: _post("/workbench/scaffold", {"kind": a.get("kind","route"), "package": a.get("package","routes.sample_hello"), "name": a.get("name","sample_hello")}))
    _areg("workbench.write", {"path":"str","content":"str","mode":"str"}, {"ok":"bool"}, 2,
          lambda a: _post("/workbench/write", {"path": a.get("path",""), "content": a.get("content",""), "mode": a.get("mode","overwrite")}))
    _areg("workbench.list", {}, {"ok":"bool"}, 1,
          lambda a: _get("/workbench/list"))
    _areg("runtime.ab.status", {}, {"ok":"bool"}, 1,
          lambda a: _get("/runtime/ab/status"))
    _areg("runtime.ab.switch", {"component":"str","slot":"str","ttl_sec":"number"}, {"ok":"bool"}, 1,
          lambda a: _post("/runtime/ab/switch", {"component": a.get("component","CORE"), "slot": a.get("slot","B"), "ttl_sec": a.get("ttl_sec")}))
    _areg("runtime.ab.commit", {"component":"str"}, {"ok":"bool"}, 1,
          lambda a: _post("/runtime/ab/commit", {"component": a.get("component","CORE")}))
    _areg("runtime.ab.rollback", {"component":"str"}, {"ok":"bool"}, 1,
          lambda a: _post("/runtime/ab/rollback", {"component": a.get("component","CORE")}))
    _areg("runtime.ab.report", {"component":"str","ok":"bool"}, {"ok":"bool"}, 1,
          lambda a: _post("/runtime/ab/report", {"component": a.get("component","CORE"), "ok": bool(a.get("ok",True))}))

_reg()
# c=a+b