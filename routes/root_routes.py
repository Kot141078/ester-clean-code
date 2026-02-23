# -*- coding: utf-8 -*-
from __future__ import annotations

"""
routes/root_routes.py — kornevye marshruty i sluzhebnye ruchki.

Naznachenie:
  • GET /        → 302 → /admin/portal
  • GET /ui      → 302 → /admin/portal
  • GET /ui/     → 302 → /admin/portal
  • GET /routes  → JSON spisok zaregistrirovannykh pravil (karta marshrutov)
  • GET /openapi.json → vydaet openapi.yaml kak JSON (esli ustanovlen PyYAML/ruamel.yaml)
  • GET /build   → kratkaya sborochnaya informatsiya

Mosty:
- Yavnyy: (UI ↔ Diagnostika) edinaya tochka vkhoda i karta marshrutov dlya debaga.
- Skrytyy #1: (Sovmestimost ↔ Loader) fayl predostavlyaet register(app), poetomu autoload_routes_fs() v app.py naydet i podklyuchit ego bez extra_routes.json.
- Skrytyy #2: (RAG/Inzheneriya ↔ Prozrachnost) /routes pozvolyaet bystro uvidet, podkhvatilis li blyuprinty (RAG, pamyat, i t.p.).

Zemnoy abzats (inzheneriya):
My ne menyaem publichnye kontrakty: dobavlyaem sluzhebnye ruchki v suschestvuyuschiy blyuprint root_bp
i registriruem ikh cherez standartnyy khuk register(app). Eto drop‑in: ni signatur, ni importov,
ni putey v drugikh modulyakh my ne trogaem.
# c=a+b
"""

import os
from typing import Any, Dict, List

from flask import Blueprint, redirect, jsonify, current_app, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -------- YAML loader (myagkaya zavisimost) --------
try:
    import yaml as _pyyaml  # type: ignore
    def _safe_load_yaml(text: str):
        return _pyyaml.safe_load(text)  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    try:
        from ruamel.yaml import YAML  # type: ignore
        _yaml = YAML(typ="safe")
        def _safe_load_yaml(text: str):
            from io import StringIO
            return _yaml.load(StringIO(text))
    except Exception:
        _pyyaml = None  # type: ignore
        def _safe_load_yaml(text: str):
            raise RuntimeError("YAML parser not available")

root_bp = Blueprint("root_bp", __name__)

# ---------- navigatsionnye redirekty ----------
@root_bp.get("/")
def root_index():
    return redirect("/admin/portal", code=302)

@root_bp.get("/ui")
@root_bp.get("/ui/")
def ui_alias():
    return redirect("/admin/portal", code=302)

# ---------- sluzhebnye ruchki v tom zhe blyuprinte ----------
@root_bp.get("/routes")
def routes_map():
    out: List[Dict[str, Any]] = []
    for r in current_app.url_map.iter_rules():
        if r.endpoint == "static":
            continue
        methods = sorted(m for m in r.methods if m not in {"HEAD", "OPTIONS"})
        out.append({"rule": str(r.rule), "endpoint": r.endpoint, "methods": methods})
    out.sort(key=lambda x: x["rule"])
    if str(request.args.get("legacy", "")).strip() == "1" or str(request.args.get("format", "")).strip().lower() == "list":
        return jsonify(out)
    return jsonify({"ok": True, "count": len(out), "routes": out})

@root_bp.get("/openapi.json")
def openapi_json():
    path = os.getenv("OPENAPI_PATH", "openapi.yaml")
    try:
        if not os.path.isfile(path):
            return jsonify({"error": f"openapi not found: {path}"}), 404
        text = open(path, "r", encoding="utf-8").read()
        try:
            data = _safe_load_yaml(text)
        except Exception as e:
            return jsonify({"error": f"yaml parser not available: {e}"}), 500
        # Esli YAML uzhe JSON-sovmestim — vernem kak est
        if isinstance(data, (dict, list)):
            return jsonify(data)
        return jsonify({"error": "openapi invalid format"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@root_bp.get("/build")
def build_info():
    return jsonify(
        {
            "name": "Ester",
            "build_date": os.getenv("BUILD_DATE", ""),
            "persist_dir": os.getenv("PERSIST_DIR", ""),
            "collection": os.getenv("COLLECTION_NAME", ""),
            "mode": os.getenv("DEFAULT_MODE", os.getenv("JUDGE_MODE", "")),
        }
    )

def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(root_bp)

def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)

__all__ = ["root_bp", "register", "init_app"]
# c=a+b
