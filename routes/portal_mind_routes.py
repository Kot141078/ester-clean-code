# -*- coding: utf-8 -*-
"""
routes/portal_mind_routes.py — stranitsy/vidzhet portala dlya myslitelnykh sobytiy RuleHub.

Endpointy:
  • /portal/mind
  • /portal/widgets/mind?limit=N&status=ok|err|blocked

Mosty:
- Yavnyy: (UX v†" Myshlenie) vizualizatsiya poslednikh resheniy Re ikh statusa.
- Skrytyy #1: (Infoteoriya v†" Diagnostika) bystryy perekhod ot simptomov k zhurnalu/eksportu.
- Skrytyy #2: (Kibernetika v†" R egulyatsiya) filtr po statusu pomogaet operativno nastraivat kvoty/prioritety.

Zemnoy abzats:
Eto «tablo v operatorskoy»: vidno, kogda mozg dumal, chto delal, skolko zanyalo i gde buksoval.

# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, render_template, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.thinking.rulehub_export import read_last  # type: ignore
except Exception:
    def read_last(limit=100, status=None): return []  # type: ignore

bp_portal_mind = Blueprint("portal_mind", __name__)

def register(app):
    app.register_blueprint(bp_portal_mind)

@bp_portal_mind.route("/portal/mind", methods=["GET"])
def portal_mind():
    limit = int(request.args.get("limit", "50"))
    status = request.args.get("status")
    rows = read_last(limit=limit, status=status)
    return render_template("portal_mind.html", rows=rows, limit=limit, status=status or "")

@bp_portal_mind.route("/portal/widgets/mind", methods=["GET"])
def portal_mind_widget():
    limit = int(request.args.get("limit", "10"))
    status = request.args.get("status")
    rows = read_last(limit=limit, status=status)
    return render_template("widgets_mind_recent.html", rows=rows)
