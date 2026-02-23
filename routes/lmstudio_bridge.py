# -*- coding: utf-8 -*-
"""
routes/lmstudio_bridge.py - UI/REST «LM Studio bridge».

Marshruty:
  • GET  /admin/lmstudio                 - HTML
  • GET  /admin/lmstudio/status          - nastroyki + kesh + resursy
  • POST /admin/lmstudio/scan            - pereskan endpointov
  • POST /admin/lmstudio/benchmark       - zamer na modeli
  • POST /admin/lmstudio/bind            - privyazat alias→endpoint+model
  • POST /admin/lmstudio/unbind          - snyat privyazku
  • GET  /admin/lmstudio/resources       - spisok privyazok

Mosty:
- Yavnyy (Integratsiya ↔ UX): odin ekran → skan, bench, privyazka.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): kesh i metriki v JSON, AB-aware bench.
- Skrytyy 2 (Praktika ↔ Sovmestimost): nichego ne trogaem v yadre; prosto otkryvaem port k lokalnomu LM Studio.

Zemnoy abzats:
Eto «panel adaptera»: podklyuchil LM Studio - uvidel modeli - zakrepil nuzhnuyu pod ponyatnym alias.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.lmstudio.bridge_settings import load_lms_settings, save_lms_settings  # type: ignore
from modules.lmstudio.bridge import scan_endpoints, benchmark, list_cached  # type: ignore
from modules.resources.lmstudio_registry import list_resources, bind_resource, unbind_resource  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lms = Blueprint("lmstudio_bridge", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_lms.get("/admin/lmstudio")
def page():
    return render_template("lmstudio_bridge.html", ab=AB)

@bp_lms.get("/admin/lmstudio/status")
def status():
    return jsonify({"ok": True, "ab": AB, "settings": load_lms_settings(), "cache": list_cached(), "resources": list_resources()})

@bp_lms.post("/admin/lmstudio/scan")
def scan():
    rep = scan_endpoints()
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_lms.post("/admin/lmstudio/benchmark")
def bench():
    body = request.get_json(silent=True) or {}
    endpoint = (body.get("endpoint") or "").strip()
    model = (body.get("model") or "").strip()
    if not endpoint or not model:
        return jsonify({"ok": False, "error": "endpoint/model required"}), 400
    rep = benchmark(endpoint, model, max_tokens=int(body.get("max_tokens", 0) or 0) or None)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep, "ab": AB})

@bp_lms.post("/admin/lmstudio/bind")
def bind():
    body = request.get_json(silent=True) or {}
    alias = (body.get("alias") or body.get("model") or "").strip()
    endpoint = (body.get("endpoint") or "").strip()
    model = (body.get("model") or "").strip()
    rep = bind_resource(alias, endpoint, model)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_lms.post("/admin/lmstudio/unbind")
def unbind():
    body = request.get_json(silent=True) or {}
    alias = (body.get("alias") or "").strip()
    if not alias: return jsonify({"ok": False, "error": "alias required"}), 400
    rep = unbind_resource(alias)
    return jsonify({"ok": bool(rep.get("ok")), "result": rep})

@bp_lms.get("/admin/lmstudio/resources")
def resources():
    return jsonify({"ok": True, "resources": list_resources()})

def register_lmstudio_bridge(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lms)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lmstudio_bridge_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lmstudio")
        def _p(): return page()

        @pref.get("/admin/lmstudio/status")
        def _s(): return status()

        @pref.post("/admin/lmstudio/scan")
        def _sc(): return scan()

        @pref.post("/admin/lmstudio/benchmark")
        def _b(): return bench()

        @pref.post("/admin/lmstudio/bind")
        def _bd(): return bind()

        @pref.post("/admin/lmstudio/unbind")
        def _ub(): return unbind()

        @pref.get("/admin/lmstudio/resources")
        def _r(): return resources()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lms)
    return app