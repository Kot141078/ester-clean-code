# -*- coding: utf-8 -*-
"""
routes/synergy_routes_plus.py - dopolnitelnye API sinergii (assign v2, overrides, roli, politiki, outcome).

MOSTY:
- (Yavnyy) /synergy/assign/v2 s ruchnymi overraydami; /synergy/outcome dlya obratnoy svyazi.
- (Skrytyy #1) /synergy/roles i /synergy/policies - prozrachnost modeli dlya operatora.
- (Skrytyy #2) /synergy/board/data - JSON dlya «shakhmatki», /synergy/assign/override - bystryy seyv fiksatsiy.

ZEMNOY ABZATs:
Daet polnyy kontur upravleniya komandoy: posmotret, zakrepit, naznachit, podtverdit uspekh/proval - i vernutsya k rabote.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any
from flask import Blueprint, request, jsonify
from modules.synergy.state_store import STORE
from modules.synergy.orchestrator_v2 import assign_v2
from modules.synergy.role_model import fit_roles_ext
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("synergy_routes_plus", __name__, url_prefix="/synergy")

@bp.route("/assign/v2", methods=["POST"])
def assign_v2_route():
    j = request.get_json(force=True, silent=True) or {}
    team_id = (j.get("team_id") or "").strip()
    overrides = j.get("overrides") or {}
    res = assign_v2(team_id, overrides)
    return (jsonify(res), 200) if res.get("ok") else (jsonify(res), 400)

@bp.route("/assign/override", methods=["POST"])
def assign_override():
    j = request.get_json(force=True, silent=True) or {}
    team_id = (j.get("team_id") or "").strip()
    ov = j.get("overrides") or {}
    t = STORE.get_team(team_id)
    if not t:
        return jsonify({"ok": False, "error": "team_not_found"}), 404
    t["overrides"] = dict(ov)
    STORE._teams[team_id] = t
    return jsonify({"ok": True, "overrides": t["overrides"]})

@bp.route("/roles", methods=["GET"])
def roles():
    # Sobiraem unifitsirovannyy spisok roley iz otsenok pervogo agenta (ili defoltnyy)
    agents = STORE.list_agents()
    if agents:
        roles = sorted(list(fit_roles_ext(agents[0]).keys()))
    else:
        roles = sorted(["operator","strategist","platform","communicator","observer","mentor","backup","qa"])
    return jsonify({"ok": True, "roles": roles})

@bp.route("/policies", methods=["GET"])
def policies():
    import os, yaml
    path = os.getenv("SYNERGY_POLICIES_PATH", "config/synergy_policies.yaml")
    data = {}
    if os.path.exists(path):
        try:
            data = yaml.safe_load(open(path,"r",encoding="utf-8")) or {}
        except Exception:
            data = {}
    return jsonify({"ok": True, "path": path, "policies": data})

@bp.route("/outcome", methods=["POST"])
def outcome():
    j = request.get_json(force=True, silent=True) or {}
    team_id = (j.get("team_id") or "").strip()
    outcome = (j.get("outcome") or "").strip().lower()
    notes = (j.get("notes") or "").strip()
    t = STORE.get_team(team_id)
    if not t:
        return jsonify({"ok": False, "error": "team_not_found"}), 404
    hist = t.setdefault("history", [])
    hist.append({"outcome": outcome, "notes": notes})
    STORE._teams[team_id] = t
    return jsonify({"ok": True, "team": team_id, "history": hist})

def register(app):
    app.register_blueprint(bp)
    return bp