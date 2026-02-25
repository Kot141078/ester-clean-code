# -*- coding: utf-8 -*-
"""routes/explain_routes.py - REST/UI dlya metaforicheskikh obyasneniy.

Mosty:
- Yavnyy: (UI ↔ Obyasnitel) - otdaem metaforu i vizualnuyu “skhemu” dlya lyubogo teksta.
- Skrytyy 1: (Memory ↔ Podacha) - auditoriya mozhet uchityvatsya upstream i peredavatsya syuda.
- Skrytyy 2: (Diagnostika ↔ Avtorskiy stil) - edinyy format obyasneniy uluchshaet doverie i povtoryaemost.

Zemnoy abzats:
Knopka “obyasni” v adminke: vstavlyaesh tekst - poluchaesh prostoe, metaforu i mini-skhemku. Bystro i po delu."""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template

from modules.cognition.explainers import explain
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("explain_routes", __name__, url_prefix="/explain")


@bp.route("/probe", methods=["GET"])
def probe():
    return jsonify({"ok": True})


@bp.route("/with_metaphor", methods=["POST"])
def with_metaphor():
    d = request.get_json(force=True, silent=True) or {}
    text = str(d.get("text", "") or "")
    audience = d.get("audience")
    return jsonify(explain(text=text, audience=audience))


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_explain.html")


def register(app):
    app.register_blueprint(bp)


# finalnaya stroka
# c=a+b