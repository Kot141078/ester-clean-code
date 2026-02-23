# -*- coding: utf-8 -*-
"""
routes/admin_proj_build.py - lokalnaya sborka paketa proekta (plan/ZIP/publikatsiya).

Marshruty:
  • GET  /admin/proj_build
  • POST /admin/proj_build/manifest    {project_dir}
  • POST /admin/proj_build/plan        {project_dir}
  • POST /admin/proj_build/build       {project_dir, publish?, out_dir?, max_bytes?, quotas?}

Mosty:
- Yavnyy (UX ↔ Sborka): «proverit → splanirovat → sobrat → opublikovat».
- Skrytyy 1 (Infoteoriya ↔ Prozrachnost): ploskie JSON, otchet ob ogranicheniyakh/kvotakh.
- Skrytyy 2 (Praktika ↔ Sovmestimost): builder i manifest v otdelnykh modulyakh; AB-rezhim uchityvaetsya.

Zemnoy abzats:
Eto «knopka upakovki»: operator bez CLI sobiraet ZIP i vklyuchaet ego v katalog dlya sosedey.

# c=a+b
"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify, render_template, request

from modules.projects.manifest import load_manifest  # type: ignore
from modules.projects.build import plan_files, build_zip  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_pb = Blueprint("admin_proj_build", __name__)
AB = (os.getenv("AB_MODE") or "A").strip().upper()

@bp_pb.get("/admin/proj_build")
def page():
    return render_template("admin_proj_build.html", ab=AB)

@bp_pb.post("/admin/proj_build/manifest")
def api_manifest():
    body = request.get_json(silent=True) or {}
    d = (body.get("project_dir") or "").strip()
    if not d: return jsonify({"ok": False, "error": "project_dir required"}), 400
    return jsonify(load_manifest(d))

@bp_pb.post("/admin/proj_build/plan")
def api_plan():
    body = request.get_json(silent=True) or {}
    d = (body.get("project_dir") or "").strip()
    if not d: return jsonify({"ok": False, "error": "project_dir required"}), 400
    return jsonify(plan_files(d, None))

@bp_pb.post("/admin/proj_build/build")
def api_build():
    body = request.get_json(silent=True) or {}
    d = (body.get("project_dir") or "").strip()
    publish = bool(body.get("publish", True))
    out_dir = body.get("out_dir") or None
    max_bytes = body.get("max_bytes")
    quotas = body.get("quotas") or {}
    if not d: return jsonify({"ok": False, "error": "project_dir required"}), 400
    return jsonify(build_zip(d, None, out_dir=out_dir, max_bytes=max_bytes, quotas=quotas, publish=publish, ab_mode=AB))

def register_admin_proj_build(app, url_prefix: str | None = None) -> None:
    app.register_blueprint(bp_pb)
    if url_prefix:
        from flask import Blueprint as _BP
        pref = _BP("admin_proj_build_pref", __name__, url_prefix=url_prefix)

        @pref.get("/admin/proj_build")
        def _p(): return page()

        @pref.post("/admin/proj_build/manifest")
        def _m(): return api_manifest()

        @pref.post("/admin/proj_build/plan")
        def _pl(): return api_plan()

        @pref.post("/admin/proj_build/build")
        def _b(): return api_build()

        app.register_blueprint(pref)
# c=a+b


def register(app):
    app.register_blueprint(bp_pb)
    return app