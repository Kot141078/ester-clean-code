# -*- coding: utf-8 -*-
"""routes/admin_hybrid.py - panel hybridnoy ocheredi: dobavit zadanie, smotret ochered, pnut TG.

Route:
  • GET /admin/hybrid - HTML
  • GET /admin/hybrid/status - svodka ocheredi
  • POST /admin/hybrid/enqueue - {type,args,targets,policy?}
  • POST /admin/hybrid/nudge_tg - {uid} → dlya state=lan_sent: prinuditelno otpravit v TG seychas

Mosty:
- Yavnyy (UX ↔ Avtomatizatsiya): edinyy remote upravleniya gibridnoy dostavkoy.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): ponyatnye JSON-otvety i yavnye sostoyaniya zadach.
- Skrytyy 2 (Praktika ↔ Sovmestimost): bez izmeneniya yadernykh kontraktov, offlayn.

Zemnoy abzats:
Eto “schitok s pereklyuchatelyami”: dobavili zadanie, smotrim kuda ushlo, pri neobkhodimosti - vruchnuyu perevodim na rezerv.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.hybrid.dispatcher import enqueue, list_queue  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_hybrid = Blueprint("admin_hybrid", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_hybrid.get("/admin/hybrid")
def page():
    return render_template("admin_hybrid.html", ab=AB)

@bp_hybrid.get("/admin/hybrid/status")
def status():
    return jsonify(list_queue())

@bp_hybrid.post("/admin/hybrid/enqueue")
def api_enqueue():
    body = request.get_json(silent=True) or {}
    jtype = (body.get("type") or "").strip()
    args  = body.get("args") or {}
    targets = body.get("targets") or {}
    policy = (body.get("policy") or "lan_then_tg").strip()
    if not jtype:
        return jsonify({"ok": False, "error": "type-required"}), 400
    return jsonify(enqueue(jtype, args, targets, policy=policy))

@bp_hybrid.post("/admin/hybrid/nudge_tg")
def nudge_tg():
    body = request.get_json(silent=True) or {}
    uid = (body.get("uid") or "").strip()
    if not uid:
        return jsonify({"ok": False, "error": "uid-required"}), 400
    # Prinuditelnyy perevod: zagruzhaem fayl, stavim tg_sent (s otpravkoy)
    import json
    from pathlib import Path
    from modules.hybrid.dispatcher import _read_json, _write_json, OUT  # type: ignore
    p = OUT / f"{uid}.json"
    if not p.exists():
        return jsonify({"ok": False, "error": "not-found"}), 404
    item = _read_json(p)
    # poprobuem otpravit v TG
    from modules.hybrid.dispatcher import _try_tg  # type: ignore
    res = _try_tg(item)
    if res.get("ok"):
        item["tg"]["uid"] = res.get("tg_uid")
        item["tg"]["attempts"] += 1
        item["tg"]["last_error"] = None
        item["state"] = "tg_sent"
        _write_json(p, item)
        return jsonify({"ok": True, "uid": uid, "tg_uid": item["tg"]["uid"]})
    else:
        item["tg"]["attempts"] += 1
        item["tg"]["last_error"] = res.get("error")
        _write_json(p, item)
        return jsonify({"ok": False, "error": res.get("error"), "uid": uid})

def register_admin_hybrid(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_hybrid)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_hybrid_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/hybrid")
        def _p(): return page()

        @pref.get("/admin/hybrid/status")
        def _s(): return status()

        @pref.post("/admin/hybrid/enqueue")
        def _e(): return api_enqueue()

        @pref.post("/admin/hybrid/nudge_tg")
        def _n(): return nudge_tg()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_hybrid)
    return app