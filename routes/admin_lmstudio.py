# -*- coding: utf-8 -*-
"""routes/admin_lmstudio.py - panel LM Studio: obnaruzhenie modeley/portov, HW-profil, aliasy, test inferensa.

Route:
  • GET /admin/lmstudio
  • GET /admin/lmstudio/status
  • POST /admin/lmstudio/aliases
  • POST /admin/lmstudio/test_infer {base?:"http://127.0.0.1:1234", prompt?}

Mosty:
- Yavnyy (UX ↔ Ekspluatatsiya): v odnom meste - vse o lokalnom inferense.
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): sukhoy rezhim A, realnye deystviya B; yavnye JSON-otvety.
- Skrytyy 2 (Praktika ↔ Sovmestimost): offlayn, stdlib; ne trogaem yadro myshleniya/pamyati/voli.

Zemnoy abzats:
This is “pult LM Studio”: vidno, kakie modeli lezhat, kakie porty slushayut, i odnoy knopkoy - test.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.lmstudio.discovery import discover  # type: ignore
from modules.hw.profile import detect_profile  # type: ignore
from modules.lmstudio.aliases import compute_aliases, write_final_resources  # type: ignore
from modules.lmstudio.test_infer import test_infer  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_lms = Blueprint("admin_lmstudio", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_lms.get("/admin/lmstudio")
def page():
    return render_template("lmstudio.html", ab=AB)

@bp_lms.get("/admin/lmstudio/status")
def status():
    disc = discover()
    prof = detect_profile()
    return jsonify({"ok": True, "ab": AB, "discovery": disc, "hw_profile": prof})

@bp_lms.post("/admin/lmstudio/aliases")
def aliases():
    disc = discover()
    prof = detect_profile()
    calc = compute_aliases(disc, prof)
    if not calc.get("ok"): return jsonify(calc), 500
    wr = write_final_resources(calc["final"])
    return jsonify({"ok": True, "calc": calc, "write": wr})

@bp_lms.post("/admin/lmstudio/test_infer")
def api_test_infer():
    body = request.get_json(silent=True) or {}
    base = (body.get("base") or f"http://127.0.0.1:{os.getenv('LMSTUDIO_PORT','1234')}").strip()
    prompt = (body.get("prompt") or "ping").strip()
    res = test_infer(base, prompt=prompt)
    return jsonify(res)

def register_admin_lmstudio(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_lms)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_lmstudio_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/lmstudio")
        def _p(): return page()

        @pref.get("/admin/lmstudio/status")
        def _s(): return status()

        @pref.post("/admin/lmstudio/aliases")
        def _a(): return aliases()

        @pref.post("/admin/lmstudio/test_infer")
        def _t(): return api_test_infer()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_lms)
    return app