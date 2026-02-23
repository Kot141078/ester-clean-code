# -*- coding: utf-8 -*-
from __future__ import annotations
import os, logging
from flask import Blueprint, render_template, make_response
from jinja2 import TemplateNotFound
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_bp = Blueprint("portal_routes_alias", __name__)
_AB = os.getenv("ESTER_PORTAL_AB", "A").upper()  # A=off, B=on

@_bp.get("/portal")
@_bp.get("/portal/")
def _portal():
    try:
        return render_template("portal.html")
    except TemplateNotFound:
        html = (
            "<!doctype html><meta charset='utf-8'>"
            "<title>Ester - Portal fallback</title>"
            "<h3>Portal vremenno nedostupen</h3>"
            "<p>Shablon <code>templates/portal.html</code> ne nayden ili ne podkhvachen.</p>"
        )
        return make_response(html, 200)
    except Exception as e:
        logging.exception("portal alias failed")
        return make_response(f"<!doctype html><meta charset='utf-8'><pre>portal error: {e}</pre>", 200)

@_bp.get("/portal/health")
def _portal_health():
    return {"ok": True, "alias": True, "ab": _AB}

def register(app):
    if _AB == "B":
        app.register_blueprint(_bp)
# c=a+b