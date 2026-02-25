# -*- coding: utf-8 -*-
"""routes/self_edit_routes.py - REST/UI dlya bezopasnoy samoredaktury koda.

Mosty:
- Yavnyy: (UI ↔ Self-Edit) - dry-run diffy i primenenie s avtokatbekom.
- Skrytyy 1: (A/B ↔ Nadezhnost) - slot A zapreschaet zapis, slot B vklyuchaet proverku i otkat pri oshibkakh.
- Skrytyy 2: (QA ↔ Dokumentatsiya) - log deystviy dostupen iz state i prigoden dlya audita.

Zemnoy abzats:
Okno “what pomenyat” i knopka “apply”. Esli vse zelenoe - izmeneniya zapisyvayutsya; esli net - otkatyvaem."""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template
from modules.meta.self_edit import dry_run, apply
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("self_edit_routes", __name__, url_prefix="/self_edit")

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.post("/dry_run")
def dry():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(dry_run(str(d.get("label","") or ""), list(d.get("edits") or [])))

@bp.post("/apply")
def ap():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(apply(str(d.get("label","") or ""), list(d.get("edits") or [])))

@bp.get("/admin")
def admin():
    return render_template("admin_self_edit.html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b