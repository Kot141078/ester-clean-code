# -*- coding: utf-8 -*-
"""
routes/synergy_board_routes.py - UI «shakhmatka roley».

MOSTY:
- (Yavnyy) /synergy/teams/board stranitsa s matritsey prigodnosti (agenty×roli) + primenenie overraydov.
- (Skrytyy #1) JSON /synergy/board/data - dlya SPA-logiki bez lishnikh zaprosov.
- (Skrytyy #2) Pri primenenii - vyzyvaet /synergy/assign/v2 i sokhranyaet overrides v komande.

ZEMNOY ABZATs:
Daet operatoru bystryy vizualnyy sposob uvidet, kto luchshe podkhodit na rol,
i vruchnuyu zakrepit klyuchevye pozitsii.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, request, render_template, jsonify
from modules.synergy.state_store import STORE
from modules.synergy.role_model import fit_roles_ext
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("synergy_board", __name__, template_folder="../templates")

@bp.route("/synergy/teams/board", methods=["GET"])
def board_page():
    return render_template("synergy_board.html", team_id=(request.args.get("team_id") or ""))

@bp.route("/synergy/board/data", methods=["GET"])
def board_data():
    team_id = (request.args.get("team_id") or "").strip()
    team = STORE.get_team(team_id) or {}
    agents = STORE.list_agents()
    scores = {a["id"]: fit_roles_ext(a) for a in agents}
    return jsonify({"ok": True, "team": team, "agents": agents, "scores": scores, "overrides": team.get("overrides") or {}, "assigned": team.get("assigned") or {}})

def register(app):
    app.register_blueprint(bp)
    return bp