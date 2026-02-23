# -*- coding: utf-8 -*-
"""
routes/p2p_consensus_routes.py - REST/UI dlya lokalnogo P2P-konsensusa.

MOSTY:
- Yavnyy: (UI ↔ Konsensus) - propose/vote/get/list/verify pod edinym prefiksom.
- Skrytyy #1: (Kriptografiya ↔ UX) - struktura dlya podpisey/proverok bez prinuzhdeniya k implementatsii.
- Skrytyy #2: (Nadezhnost ↔ Offlayn) - myagkie zaglushki pri otsutstvii modules.p2p_consensus.

ZEMNOY ABZATs:
Prostoy «kvorum po mestu»: neskolko uzlov podtverzhdayut fakt bez vneshney seti. Udobno offlayn.
# c=a+b
"""
from __future__ import annotations

from flask import Blueprint, request, jsonify, render_template
from werkzeug.wrappers import Response as _Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("p2p_consensus_routes", __name__, url_prefix="/p2p_consensus")

# Popytka importa realnoy logiki; esli net - myagkie zaglushki
try:
    from modules.p2p_consensus import propose, vote, get, list_ids, verify  # type: ignore
except Exception:
    def propose(id_: str, text: str, author=None):
        return {"ok": False, "error": "p2p_consensus_unavailable", "op": "propose", "id": id_, "text": text}
    def vote(id_: str, value: int, peer_id=None):
        return {"ok": False, "error": "p2p_consensus_unavailable", "op": "vote", "id": id_, "value": value}
    def get(id_: str):
        return {"ok": False, "error": "p2p_consensus_unavailable", "op": "get", "id": id_}
    def list_ids():
        return {"ok": True, "items": []}
    def verify(id_: str):
        return {"ok": False, "error": "p2p_consensus_unavailable", "op": "verify", "id": id_}

@bp.get("/probe")
def probe():
    return jsonify({"ok": True})

@bp.post("/propose")
def propose_():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(propose(str(d.get("id", "") or ""), str(d.get("text", "") or ""), d.get("author")))

@bp.post("/vote")
def vote_():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(vote(str(d.get("id", "") or ""), int(d.get("value", 1)), d.get("peer_id")))

@bp.get("/get")
def get_():
    return jsonify(get(str(request.args.get("id", "") or "")))

@bp.get("/list")
def list_():
    return jsonify(list_ids())

@bp.get("/verify")
def verify_():
    return jsonify(verify(str(request.args.get("id", "") or "")))

@bp.get("/admin")
def admin():
    # Esli shablona net - otdaem prostuyu HTML-stranitsu s ssylkami na ruchki
    try:
        return render_template("admin_p2p.html")
    except Exception:
        html = """<!doctype html><html><body>
        <h3>P2P Consensus Admin</h3>
        <ul>
          <li>POST /p2p_consensus/propose {id,text,author}</li>
          <li>POST /p2p_consensus/vote {id,value,peer_id}</li>
          <li>GET  /p2p_consensus/get?id=...</li>
          <li>GET  /p2p_consensus/list</li>
          <li>GET  /p2p_consensus/verify?id=...</li>
        </ul>
        </body></html>"""
        return _Response(html, mimetype="text/html")

def register(app):
    app.register_blueprint(bp)

# finalnaya stroka - bezopasno, v kommentarii:
# c=a+b