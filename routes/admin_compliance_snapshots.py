# -*- coding: utf-8 -*-
"""routes/admin_compliance_snapshots.py - UI/API snapshotov Compliance.

Route:
  • GET /admin/portable/snapshots - stranitsa
  • GET /admin/portable/snapshots/list - spisok dostupnykh snapshotov (USB + lokalno)
  • POST /admin/portable/snapshots/make - sdelat snapshot (AB=A → dry)
  • POST /admin/portable/snapshots/diff - sravnit dva snapshota (poslednie dva po umolchaniyu)

Mosty:
- Yavnyy (Snimok ↔ Sravnenie): po knopke delaem snimok i tut zhe mozhem sravnit s predyduschim.
- Skrytyy 1 (Infoteoriya): unifitsirovannyy format JSON, predskazuemye polya i delty.
- Skrytyy 2 (Praktika): zapis tolko v AB=B, offlayn, yadro Ester ne trogaem.

Zemnoy abzats:
This is “tekhprofile s probegom”: khranim izmeneniya ekspluatatsii v faylakh, chtoby videt trendy i regressii bez setey i BD.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.compliance.snapshot import (  # type: ignore
    list_snapshots,
    save_snapshot,
    load_snapshot,
    diff_snapshots,
)

bp = Blueprint("admin_compliance_snapshots", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp.get("/admin/portable/snapshots")
def page():
    return render_template("admin_compliance_snapshots.html", ab=AB)

@bp.get("/admin/portable/snapshots/list")
def lst():
    return jsonify({"ok": True, "ab": AB, "snapshots": list_snapshots()})

@bp.post("/admin/portable/snapshots/make")
def make():
    meta = (request.get_json(silent=True) or {}).get("meta") or {}
    res = save_snapshot(meta)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

@bp.post("/admin/portable/snapshots/diff")
def diff():
    body = request.get_json(silent=True) or {}
    a_path = (body.get("a") or "").strip()
    b_path = (body.get("b") or "").strip()
    # If not specified, take the last two from the USB, then local ones
    snaps = list_snapshots()
    ordered = snaps.get("usb", []) + snaps.get("local", [])
    if not a_path or not b_path:
        if len(ordered) < 2:
            return jsonify({"ok": False, "error": "not-enough-snapshots"}), 400
        a_path = a_path or ordered[1]["path"]
        b_path = b_path or ordered[0]["path"]
    a = load_snapshot(a_path)
    b = load_snapshot(b_path)
    rep = diff_snapshots(a, b)
    return jsonify({"ok": True, "ab": AB, "diff": rep, "a": {"path": a_path}, "b": {"path": b_path}})

def register_admin_compliance_snapshots(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_compliance_snapshots_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/portable/snapshots")
        def _p(): return page()
        @pref.get("/admin/portable/snapshots/list")
        def _l(): return lst()
        @pref.post("/admin/portable/snapshots/make")
        def _m(): return make()
        @pref.post("/admin/portable/snapshots/diff")
        def _d(): return diff()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app
