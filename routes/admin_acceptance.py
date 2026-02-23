# -*- coding: utf-8 -*-
"""
Admin Acceptance - finalnaya priemka (UI).

Most (yavnyy):
- (Kibernetika ↔ Kontrol) Knopka «Snyat snapshot» i vidimyy rezhim A/B.

Mosty (skrytye):
- (Infoteoriya ↔ Ekonomika) Otchet v kanonichnom JSON oblegchaet obmen i arkhivirovanie.
- (Logika ↔ UX) Chek-list na odnoy stranitse fokusiruet vnimanie na klyuchevykh stsenariyakh.

Zemnoy abzats:
Stranitsa pokazyvaet chek-list priemki i zapuskaet sbor itogovogo snapshota.
V A - tolko prevyu na ekrane, v B - zapis fayla `ESTER/reports/final_compliance.json`.

# c=a+b
"""
from __future__ import annotations

import os
from pathlib import Path
from flask import Blueprint, jsonify, render_template

from modules.acceptance.snapshot import gather_snapshot, gather_and_maybe_write
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("admin_acceptance", __name__, url_prefix="/admin/acceptance")

AB_MODE = (os.getenv("AB_MODE") or "A").strip().upper()
CHECKLIST_PATH = Path("docs/acceptance_checklist.md")

@bp.get("/")
def page():
    try:
        checklist_md = CHECKLIST_PATH.read_text(encoding="utf-8")
    except Exception:
        checklist_md = "# acceptance_checklist.md ne nayden\n"
    return render_template("admin_acceptance.html", ab_mode=AB_MODE, checklist_md=checklist_md)

@bp.post("/snapshot")
def api_snapshot():
    # Esli AB=B - proizoydet zapis; inache vernem prevyu
    res = gather_and_maybe_write()
    return jsonify(res)

def register(app):  # pragma: no cover
    app.register_blueprint(bp)

def init_app(app):  # pragma: no cover
    app.register_blueprint(bp)
# c=a+b