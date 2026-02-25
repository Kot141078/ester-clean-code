# -*- coding: utf-8 -*-
"""routes/provenance_routes.py - REST-ruchki dlya raboty s “profileami znaniy”.

Endpoint:
  • POST /mem/provenance/enrich {record, index?} v†' record s meta.provenance
  • POST /mem/provenance/verify {record} v†' ok/issues/passport
  • GET /mem/provenance/stats v†' svodka po indexed profileam (dublikaty)

RBAC:
  • enrich/stats - 'operator' (zapis v indexes), verify - 'viewer'.

Mosty:
- Yavnyy: (Memory v†" Inzheneriya) bystraya normalizatsiya zapisey pered sokhraneniem ili obmenom.
- Skrytyy #1: (Infoteoriya v†" Nadezhnost) dublikaty po sha256 vidny srazu.
- Skrytyy #2: (Kibernetika v†" Kontrol) rol ogranichivaet massovuyu indeksatsiyu.

Zemnoy abzats:
Eto kak postavit shtamp v kartochke tovara Re polozhit kopiyu v zhurnal — potom bystro naydem Re proverim.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory.provenance import enrich_record, verify_record, stats_index  # type: ignore
except Exception:
    enrich_record = verify_record = stats_index = None  # type: ignore

try:
    from modules.security.rbac import require_role  # type: ignore
except Exception:
    def require_role(_r):  # type: ignore
        def deco(fn): return fn
        return deco

bp_provenance = Blueprint("provenance", __name__)

def register(app):
    app.register_blueprint(bp_provenance)

@bp_provenance.route("/mem/provenance/enrich", methods=["POST"])
@require_role("operator")
def api_enrich():
    if enrich_record is None:
        return jsonify({"ok": False, "error": "provenance module not available"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    rec = data.get("record") or {}
    index = bool(data.get("index", False))
    out = enrich_record(rec, index=index)
    return jsonify({"ok": True, "record": out})

@bp_provenance.route("/mem/provenance/verify", methods=["POST"])
def api_verify():
    if verify_record is None:
        return jsonify({"ok": False, "error": "provenance module not available"}), 500
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    rec = data.get("record") or {}
    out = verify_record(rec)
    return jsonify(out)

@bp_provenance.route("/mem/provenance/stats", methods=["GET"])
@require_role("operator")
def api_stats():
    if stats_index is None:
        return jsonify({"ok": False, "error": "provenance module not available"}), 500
# return jsonify(stats_index())