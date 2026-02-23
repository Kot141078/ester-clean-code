
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, io, traceback
from flask import Blueprint, current_app, jsonify, make_response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
try:
    from flask import render_template
except Exception:
    render_template = None

_AB = os.getenv("ESTER_PORTAL_ALIAS2_AB", "B").upper()
_bp = Blueprint("portal_alias2", __name__)

@_bp.get("/_alias2/portal/health")
def portal_health():
    return jsonify(ok=True, ab=_AB, template_dir=current_app.template_folder, blueprints=list(current_app.blueprints.keys()))

@_bp.get("/_alias2/portal")
def portal_render():
    # 1) Pytaemsya otdat templates/portal.html
    if render_template is not None:
        try:
            html = render_template("portal.html")
            r = make_response(html, 200)
            r.headers["X-Ester-Portal-Alias2"] = "rendered"
            return r
        except Exception as e:
            # 2) Folbek: minimalnaya stranitsa bez zavisimostey
            _log("portal_render fallback: %r" % e)
    # 3) Minimalnyy HTML (bez 500)
    html = u"<!doctype html><html><head><meta charset='utf-8'><title>Ester Portal (alias2)</title></head>" \
           u"<body><h1>Ester Portal (alias2)</h1><p>Shablon portal.html nedostupen, pokazan fallback.</p></body></html>"
    r = make_response(html, 200)
    r.headers["X-Ester-Portal-Alias2"] = "fallback"
    return r

def _log(msg):
    try:
        os.makedirs("data", exist_ok=True)
        with io.open("data/bringup_after_chain.log", "a", encoding="utf-8") as f:
            f.write(u"[PortalAlias2] %s\n" % msg)
    except Exception:
        pass

def register(app):
    if _AB == "B":
        app.register_blueprint(_bp)
