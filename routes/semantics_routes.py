# -*- coding: utf-8 -*-
"""
routes/semantics_routes.py - REST/UI dlya ontologicheskogo kesha.

Mosty:
- Yavnyy: (UI ↔ Ontologiya) - CRUD terminov i reconcile teksta.
- Skrytyy 1: (Memory ↔ Kommunikatsiya) - stabiliziruem terminy dlya interfeysa i logov.
- Skrytyy 2: (Dannye ↔ Spravochnik) - ontologiya khranitsya ryadom s sostoyaniem i ne lomaet suschestvuyuschie parsery.

Zemnoy abzats:
Forma, gde mozhno dobavit termin, sinonimy i na letu «primirit» lyuboy tekst so slovarem.
Udobno pered rassylkami i otchetami, chtoby terminologiya ne «plavala».
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template
from typing import List

from modules.semantics.ontology_cache import define_term, get_term, list_terms, reconcile_text
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("semantics_routes", __name__, url_prefix="/semantics")

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.get("/get")
def get_():
    name = str(request.args.get("name","") or "")
    return jsonify(get_term(name))

@bp.get("/list")
def list_():
    limit = int(request.args.get("limit", 200))
    return jsonify(list_terms(limit=limit))

@bp.post("/define")
def define():
    d = request.get_json(force=True, silent=True) or {}
    name = str(d.get("name","") or "")
    definition = str(d.get("definition","") or "")
    synonyms: List[str] = list(d.get("synonyms") or [])
    return jsonify(define_term(name=name, definition=definition, synonyms=synonyms))

@bp.post("/reconcile")
def rec():
    d = request.get_json(force=True, silent=True) or {}
    text = str(d.get("text","") or "")
    return jsonify(reconcile_text(text))

@bp.get("/admin")
def admin():
    # prostoy self-contained HTML bez otdelnogo shablona
    return render_template("admin_semantics.html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka
# c=a+b