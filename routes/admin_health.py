# -*- coding: utf-8 -*-
"""routes/admin_health.py - Self-Check panel: svodka health, uglublennye proverki, avtopochinka, eksport otcheta.

Route:
  • GET /admin/health - HTML
  • GET /admin/health/status - sobrat obschiy otchet (deep=false)
  • POST /admin/health/selfcheck - deep=true (LM Studio ping pri AB=B)
  • POST /admin/health/auto_fix - vypolnit deystviya (AB-aware)
  • POST /admin/health/export - eksport otcheta na fleshku

Mosty:
- Yavnyy (Nablyudenie ↔ Deystvie): “vizhu problemu → chinyu” - v odnom okne, s A/B predokhranitelem.
- Skrytyy 1 (Infoteoriya ↔ Nadezhnost): deep-check i pochinka atomically, otchet - chitaemyy JSON.
- Skrytyy 2 (Praktika ↔ Sovmestimost): vse vyzovy myagko degradiruyut (“skipped”) bez oshibok.

Zemnoy abzats:
Eto “tekhpanel”: daet tselostnuyu kartinku uzla i pozvolyaet v paru klikov popravit chastye sboi - bez tantsev s bubnom.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.selfcheck.health_probe import build_report  # type: ignore
from modules.selfcheck.auto_fix import restart_sidecar, clear_inboxes, rebuild_indices, rebind_lmstudio, rescan_usb_once, export_report  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_health = Blueprint("admin_health", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_health.get("/admin/health")
def page():
    return render_template("admin_health.html", ab=AB)

@bp_health.get("/admin/health/status")
def status():
    deep = bool(request.args.get("deep", "0") == "1")
    return jsonify(build_report(deep=deep))

@bp_health.post("/admin/health/selfcheck")
def selfcheck():
    return jsonify(build_report(deep=True))

@bp_health.post("/admin/health/auto_fix")
def auto_fix():
    body = request.get_json(silent=True) or {}
    actions = body.get("actions") or []
    out = {}
    for name in actions:
        if name == "restart_sidecar": out["restart_sidecar"] = restart_sidecar()
        elif name == "clear_inboxes": out["clear_inboxes"] = clear_inboxes()
        elif name == "rebuild_indices": out["rebuild_indices"] = rebuild_indices()
        elif name == "rebind_lmstudio": out["rebind_lmstudio"] = rebind_lmstudio()
        elif name == "rescan_usb_once": out["rescan_usb_once"] = rescan_usb_once()
    return jsonify({"ok": True, "results": out, "ab": AB})

@bp_health.post("/admin/health/export")
def export():
    body = request.get_json(silent=True) or {}
    mount = (body.get("mount") or "").strip()
    if not mount: return jsonify({"ok": False, "error": "mount required"}), 400
    rep = build_report(deep=True)
    return jsonify(export_report(mount, rep))
    
def register_admin_health(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_health)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_health_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/health")
        def _p(): return page()

        @pref.get("/admin/health/status")
        def _s(): return status()

        @pref.post("/admin/health/selfcheck")
        def _sc(): return selfcheck()

        @pref.post("/admin/health/auto_fix")
        def _af(): return auto_fix()

        @pref.post("/admin/health/export")
        def _e(): return export()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_health)
    return app