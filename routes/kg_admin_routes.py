# -*- coding: utf-8 -*-
"""routes/kg_admin_routes.py - administrative operations dlya KG/GC/Rebuild.

Route:
  POST /kg/admin/repair - chinit KG invarianty (merge/dedup po rebram)
  POST /kg/admin/decay_gc - ubyvanie/GC s parametrami (sm. DecayRules)
  POST /kg/admin/rebuild_all - skvoznoy Rebuild/Repair: Structured + Vector + KG

Mosty:
- Yavnyy: Memory (KGStore/DecayGC) ↔ Operatsii (REST) - edinaya panel admina.
- Skrytyy #1: Infoteoriya (Cover-Thomas) - “decay” snizhaet noise vesa reber.
- Skrytyy #2: Kibernetika (Ashby) - repair/GC derzhat graf v ustoychivom sostoyanii.

Zemnoy abzats:
Podumay o KG kak o “limfosisteme”: repair - sanobrabotka, decay - natural decay,
GC - vyvedenie musora; rebuild_all - “polnaya sanatsiya” po vsem organam (khranilischam).

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request

from memory.decay_gc import DecayGC, DecayRules
from memory.kg_store import KGStore
from modules.rebuild_repair import RebuildRepairEngine
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

kg_admin_bp = Blueprint("kg_admin", __name__, url_prefix="/kg/admin")


@kg_admin_bp.post("/repair")
def kg_repair():
    try:
        kg = KGStore()
        res = kg.repair()
        return jsonify({"ok": True, "kg": res})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@kg_admin_bp.post("/decay_gc")
def kg_decay_gc():
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        rules = DecayRules(
            half_life_s=float(data.get("half_life_s") or 7 * 24 * 3600),
            min_weight=float(data.get("min_weight") or 0.05),
            gc_edge_min_age_s=float(data.get("gc_edge_min_age_s") or 2 * 24 * 3600),
            gc_edge_weight_threshold=float(data.get("gc_edge_weight_threshold") or 0.08),
            gc_node_min_age_s=float(data.get("gc_node_min_age_s") or 3 * 24 * 3600),
        )
        rep = DecayGC().apply(rules)
        return jsonify({"ok": True, "report": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


@kg_admin_bp.post("/rebuild_all")
def kg_rebuild_all():
    try:
        eng = RebuildRepairEngine()
        rep = eng.run_full()
        return jsonify({"ok": True, "report": rep, "status": "done"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


def register_kg_admin_routes(app) -> None:  # pragma: no cover
    """Compatible blueprint registration (project contract)."""
    app.register_blueprint(kg_admin_bp)


# Unifitsirovannye khuki project (drop-in)
def register(app) -> None:  # pragma: no cover
    app.register_blueprint(kg_admin_bp)


def init_app(app) -> None:  # pragma: no cover
    app.register_blueprint(kg_admin_bp)


__all__ = ["kg_admin_bp", "register_kg_admin_routes", "register", "init_app"]


def register(app):
    app.register_blueprint(kg_admin_bp)
    return app