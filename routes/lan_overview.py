# -*- coding: utf-8 -*-
"""routes/lan_overview.py - UI/REST “Svodka seti”: topologiya, versii, pull best, mini-dashbord kvot.

Route:
  • GET /admin/lan/overview - HTML
  • GET /admin/lan/overview/status - snapshot()
  • POST /admin/lan/overview/pull_best - enqueue pull k luchshemu istochniku (uchityvaet AB_MODE)

Mosty:
- Yavnyy (UX ↔ Orkestratsiya): odin ekran s kartinkoy seti i knopkoy “zabrat u luchshego”.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): deystviya idut cherez ochered job_queue (prozrachnyy JSON i kvoty).
- Skrytyy 2 (Praktika ↔ Sovmestimost): drop-in; polzuem uzhe suschestvuyuschie mekhanizmy paketov-35/36.

Zemnoy abzats:
This is “panel operatora”: see kto ryadom, kakaya versiya u kogo, i zaberi kod ot blizhayshego/luchshego istochnika v odin klik.

# c=a+b"""
from __future__ import annotations

import os
from flask import Blueprint, jsonify, render_template, request

from modules.lan.overview import snapshot, choose_best  # type: ignore
from modules.lan.job_queue import enqueue  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lanov = Blueprint("lan_overview", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_lanov.get("/admin/lan/overview")
def page():
    return render_template("lan_overview.html", ab=AB)

@bp_lanov.get("/admin/lan/overview/status")
def api_status():
    return jsonify({"ok": True, "ab": AB, "data": snapshot()})

@bp_lanov.post("/admin/lan/overview/pull_best")
def pull_best():
    body = request.get_json(silent=True) or {}
    min_version = (body.get("min_version") or "").strip() or None
    best = choose_best(min_version=min_version)
    if not best:
        return jsonify({"ok": False, "error": "no-source"}), 404
    if AB != "B":
        return jsonify({"ok": True, "dry": True, "peer": best.get("base_url")})
    jid = enqueue({"type":"pull","args":{"peer": best.get("base_url")}, "pri": 120})
    return jsonify({"ok": True, "job_id": jid, "peer": best.get("base_url")})

def register_lan_overview(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lanov)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("lan_overview_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lan/overview")
        def _p(): return page()

        @pref.get("/admin/lan/overview/status")
        def _s(): return api_status()

        @pref.post("/admin/lan/overview/pull_best")
        def _pb(): return pull_best()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lanov)
    return app