# -*- coding: utf-8 -*-
"""routes/codegate_routes.py - REST: podpis/verka + secure-registratsiya proekta iz garazha.

Mosty:
- Yavnyy: (Veb ↔ Bezopasnost) odin sloy dlya HMAC-podpisey i ikh validatsii.
- Skrytyy #1: (Garazh ↔ Registratsiya) bezopasnaya registratsiya cherez AutoDiscover s proverkoy podpisi.
- Skrytyy #2: (Profile ↔ Trassirovka) vse resheniya fiksiruyutsya.

Zemnoy abzats:
Pered tem kak vpustit novuyu “korobku” vnutr - proveryaem plombu. Esli vse skhoditsya, podklyuchaem.

# c=a+b"""
from __future__ import annotations
from flask import Blueprint, jsonify, request
import os, json, urllib.request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("codegate_routes", __name__)

def register(app):
    app.register_blueprint(bp)

try:
    from modules.security.codegate import sign as _sign, verify as _verify  # type: ignore
except Exception:
    _sign=_verify=None  # type: ignore

def _passport(note: str, meta: dict):
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(note, meta, "security://codegate")
    except Exception:
        pass

def _discover_register(modname: str)->dict:
    data=json.dumps({"modules":[modname]}).encode("utf-8")
    req=urllib.request.Request("http://127.0.0.1:8000/app/discover/register", data=data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        import json as _j; return _j.loads(r.read().decode("utf-8"))

@bp.route("/codegate/sign", methods=["POST"])
def api_sign():
    if _sign is None: return jsonify({"ok": False, "error":"codegate_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_sign(str(d.get("path","")), str(d.get("note",""))))

@bp.route("/codegate/verify", methods=["POST"])
def api_verify():
    if _verify is None: return jsonify({"ok": False, "error":"codegate_unavailable"}), 500
    d=request.get_json(True, True) or {}
    return jsonify(_verify(str(d.get("path",""))))

@bp.route("/garage/project/register_secure", methods=["POST"])
def api_register_secure():
    """It waits for the project name from GARAGE_REG, checks the signature of the project folder and only after that registers the module."""
    d=request.get_json(True, True) or {}
    name=str(d.get("name",""))
    # reading the garage register
    import json as _j
    reg_path=os.getenv("GARAGE_REG","data/garage/registry.json")
    if not os.path.isfile(reg_path):
        return jsonify({"ok": False, "error":"garage_registry_missing"}), 500
    reg=_j.load(open(reg_path,"r",encoding="utf-8"))
    proj=(reg.get("projects") or {}).get(name)
    if not proj:
        return jsonify({"ok": False, "error":"project_not_found"}), 404
    proj_dir=proj.get("dir",""); module=proj.get("module","")
    # signature verification
    from modules.security.codegate import verify, ENFORCE  # type: ignore
    v=verify(proj_dir)
    if not v.get("ok"):
        _passport("codegate_deny_register", {"name": name, "reason": v.get("reason")})
        if ENFORCE:
            return jsonify({"ok": False, "error":"verify_failed", "detail": v}), 403
    # registratsiya
    rep=_discover_register(module)
    _passport("codegate_register", {"name": name, "module": module, "verified": v.get("verified",False)})
    return jsonify({"ok": True, "module": module, "verified": v.get("verified",False), "discover": rep})
# c=a+b