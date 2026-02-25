# -*- coding: utf-8 -*-
"""routes/admin_compliance_exchange.py - UI/API exchange snapshotami cherez payloads i LAN-drop.

Route:
  • GET /admin/portable/exchange - stranitsa
  • GET /admin/portable/exchange/list - spisok payloads (inbox/outbox)
  • POST /admin/portable/exchange/export - eksportirovat posledniy snapshot v outbox
  • POST /admin/portable/exchange/import - importirovat vse iz inbox v reports
  • POST /admin/portable/exchange/send_lan - {path} → skopirovat fayl v LAN_DROP_DIR (faylom, bez setey)

Mosty:
- Yavnyy (perenos ↔ ekspluatatsiya): iz UI vse delaetsya v odin klik.
- Skrytyy 1 (Infoteoriya): statusy dry/ok i puti naznacheniya delayut protsess nablyudaemym.
- Skrytyy 2 (Praktika): chistyy stdlib/offlayn; zapis tolko v AB=B; yadro Ester ne zatragivaem.

Zemnoy abzats:
Eto “okno vydachi i priema”: kladem konvert v outbox, zabiraem iz inbox, a v LAN-korobku - kopiey fayla.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.compliance.exchange import (  # type: ignore
    list_payloads,
    export_snapshot_to_outbox,
    import_all_from_inbox,
    send_to_lan,
)

bp = Blueprint("admin_compliance_exchange", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp.get("/admin/portable/exchange")
def page():
    return render_template("admin_compliance_exchange.html", ab=AB)

@bp.get("/admin/portable/exchange/list")
def lst():
    return jsonify({"ok": True, "ab": AB, "payloads": list_payloads()})

@bp.post("/admin/portable/exchange/export")
def do_export():
    body = request.get_json(silent=True) or {}
    snap_path = body.get("snapshot_path")
    res = export_snapshot_to_outbox(snap_path)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

@bp.post("/admin/portable/exchange/import")
def do_import():
    res = import_all_from_inbox()
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

@bp.post("/admin/portable/exchange/send_lan")
def do_send_lan():
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()
    res = send_to_lan(path)
    code = 200 if res.get("ok") else 400
    return jsonify({"ok": bool(res.get("ok")), "ab": AB, "result": res}), code

def register_admin_compliance_exchange(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_compliance_exchange_pref", __name__, url_prefix=url_prefix)
        @pref.get("/admin/portable/exchange")
        def _p(): return page()
        @pref.get("/admin/portable/exchange/list")
        def _l(): return lst()
        @pref.post("/admin/portable/exchange/export")
        def _e(): return do_export()
        @pref.post("/admin/portable/exchange/import")
        def _i(): return do_import()
        @pref.post("/admin/portable/exchange/send_lan")
        def _s(): return do_send_lan()
        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp)
    return app
