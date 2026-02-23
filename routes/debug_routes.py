# -*- coding: utf-8 -*-
"""
routes/debug_routes.py - bazovye otladochnye ruchki.

MOSTY:
- (Yavnyy) GET /debug/env (bezopasno maskiruet sekrety), POST /debug/echo, GET /debug/threads.
- (Skrytyy #1) /debug/env uvazhaet spisok klyuchey i ne raskryvaet znacheniya s *KEY/TOKEN/SECRET*.
- (Skrytyy #2) Polezno pri bystroy diagnostike bez dostupa k terminalu.

ZEMNOY ABZATs:
Eto «servisnaya dvertsa»: posmotret, chto pod kapotom, i proverit trakt dannykh.

# c=a+b
"""
from __future__ import annotations
import os, threading
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("debug_routes", __name__, url_prefix="/debug")

def register(app):
    app.register_blueprint(bp)

def _mask(k: str, v: str) -> str:
    if any(s in k for s in ("KEY","TOKEN","SECRET","PASSWORD","PASS","PRIVATE","SIGNING")):
        return "<REDACTED>" if v else ""
    return v

@bp.get("/env")
def env():
    keys = sorted(set(list(os.environ.keys())))
    out = {k: _mask(k, os.getenv(k,"")) for k in keys}
    return jsonify({"ok": True, "env": out})

@bp.post("/echo")
def echo():
    return jsonify({"ok": True, "headers": dict(request.headers), "json": (request.get_json(silent=True) or {}), "args": request.args.to_dict()})

@bp.get("/threads")
def threads():
    names = [t.name for t in threading.enumerate()]
    return jsonify({"ok": True, "threads": names})
# c=a+b