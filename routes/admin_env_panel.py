# -*- coding: utf-8 -*-
"""routes/admin_env_panel.py - ENV-panel: UI/API dlya importa recommend.env, predprosmotra i zapisi active.env.

Route:
  • GET /admin/env - stranitsa
  • GET /admin/env/recommend - zagruzit tekst recommend.env (esli est na USB)
  • POST /admin/env/preview - {text?} → diff s tekuschim okruzheniem
  • POST /admin/env/apply - {vars?} → zapisat ESTER/portable/active.env (AB=A → dry)

Mosty:
- Yavnyy (konfig → deystvie): odin ekran ot zagruzki recommend.env do gotovogo active.env.
- Skrytyy 1 (Infoteoriya): determinirovannyy diff umenshaet “ruchnye” oshibki.
- Skrytyy 2 (Praktika): zapis tolko v portable/*, stdlib, offlayn, AB-guard.

Zemnoy abzats:
This is “panel nastroyki”: vidno, chto pomenyaetsya, i aktivnyy nabor pishetsya otdelnym faylom bez troganiya protsessa.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.env.panel import (  # type: ignore
    parse_env_text,
    load_recommend_env,
    current_env,
    diff_env,
    write_active_env,
)

bp = Blueprint("admin_env_panel", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp.get("/admin/env")
def page():
    return render_template("admin_env.html", ab=AB)

@bp.get("/admin/env/recommend")
def get_recommend():
    info = load_recommend_env()
    return jsonify(info)

@bp.post("/admin/env/preview")
def preview():
    body = request.get_json(silent=True) or {}
    text = body.get("text") or ""
    if not text:
        rec = load_recommend_env()
        if rec.get("ok") and rec.get("text"):
            text = rec["text"]  # type: ignore
    vars_file = parse_env_text(text)
    cur = current_env(list(vars_file.keys()))
    d = diff_env(vars_file, cur)
    return jsonify({"ok": True, "ab": AB, "vars_count": len(vars_file), "diff": d})

@bp.post("/admin/env/apply")
def apply():
    body = request.get_json(silent=True) or {}
    vars_obj = body.get("vars") or {}
    if not isinstance(vars_obj, dict) or not vars_obj:
        return jsonify({"ok": False, "error": "vars-required"}), 400
    res = write_active_env({str(k): str(v) for k, v in vars_obj.items()})
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

def register_admin_env_panel(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_env_panel_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/env")
        def _p(): return page()
        @pref.get("/admin/env/recommend")
        def _gr(): return get_recommend()
        @pref.post("/admin/env/preview")
        def _pr(): return preview()
        @pref.post("/admin/env/apply")
        def _ap(): return apply()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app
