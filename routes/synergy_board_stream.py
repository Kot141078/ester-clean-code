# -*- coding: utf-8 -*-
"""
routes/synergy_board_stream.py - Server-Sent Events dlya «Shakhmatki» i agregaty.

MOSTY:
- (Yavnyy) /synergy/board/stream - event: update pri izmenenii STORE._v ili naznacheniy komandy.
- (Skrytyy #1) /synergy/board/aggregate - top-kandidaty po rolyam, nagruzka agentov, riski platformy.
- (Skrytyy #2) Heartbeat event: ping dlya podderzhaniya soedineniya i prostogo L7-Health.

ZEMNOY ABZATs:
«Shakhmatka» sama ozhivaet: izmeneniya (novye agenty, perestanovki roley, telemetriya ustroystv) avtomaticheski
podtyagivayutsya vo front bez perezagruzki stranitsy. Agregaty pomogayut bystro ponyat kartinu.

# c=a+b
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Generator, List, Optional

from flask import Blueprint, Response, jsonify, request

from modules.synergy.state_store import STORE
from modules.synergy.role_model import fit_roles_ext
from modules.synergy.capability_infer import infer_capabilities
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("synergy_board_stream", __name__, url_prefix="/synergy")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _snapshot_team(team_id: str) -> Dict[str, Any]:
    team = STORE.get_team(team_id) or {}
    agents = STORE.list_agents()
    scores = {a["id"]: fit_roles_ext(a) for a in agents}
    return {
        "team": team,
        "assigned": (team.get("assigned") or {}),
        "overrides": (team.get("overrides") or {}),
        "scores": scores,
        "agents_count": len(agents),
        "v": STORE.snapshot()["v"],
        "ts": _now_ms(),
    }


def _sse_pack(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@bp.route("/board/stream", methods=["GET"])
def board_stream():
    """
    SSE-potok sobytiy dlya konkretnoy team_id.
    Otdaet:
      - event: update - pri izmenenii STORE._v ili naznacheniya/overraydov vybrannoy komandy
      - event: ping   - raz v heartbeat_sec
    """
    team_id = (request.args.get("team_id") or "").strip()
    if not team_id:
        return jsonify({"ok": False, "error": "team_id_required"}), 400

    heartbeat_sec = int(os.getenv("SYNERGY_SSE_HEARTBEAT_SEC", "15"))
    poll_ms = int(os.getenv("SYNERGY_SSE_POLL_MS", "750"))

    def gen() -> Generator[str, None, None]:
        last_v = -1
        last_assigned = None
        last_ping = 0
        # nachalnyy snimok
        snap = _snapshot_team(team_id)
        last_v = snap["v"]
        last_assigned = dict(snap["assigned"])
        yield _sse_pack("update", {"team_id": team_id, **snap})
        while True:
            time.sleep(poll_ms / 1000.0)
            v = STORE.snapshot()["v"]
            # heartbeat
            if time.time() - last_ping > heartbeat_sec:
                last_ping = time.time()
                yield _sse_pack("ping", {"ts": _now_ms(), "team_id": team_id})
            # izmeneniya
            team = STORE.get_team(team_id) or {}
            assigned = dict(team.get("assigned") or {})
            if v != last_v or assigned != last_assigned:
                last_v = v
                last_assigned = dict(assigned)
                snap = _snapshot_team(team_id)
                yield _sse_pack("update", {"team_id": team_id, **snap})

    return Response(gen(), mimetype="text/event-stream")


@bp.route("/board/aggregate", methods=["GET"])
def board_aggregate():
    """
    Agregaty dlya bordy:
      - role_candidates: top-3 po kazhdoy roli
      - agent_load: {agent_id: n_roles}
      - risks: evristiki po naznachennoy platforme
    """
    team_id = (request.args.get("team_id") or "").strip()
    if not team_id:
        return jsonify({"ok": False, "error": "team_id_required"}), 400

    team = STORE.get_team(team_id) or {}
    roles = list(team.get("roles_needed") or [])
    assigned = dict(team.get("assigned") or {})
    agents = STORE.list_agents()
    scores = {a["id"]: fit_roles_ext(a) for a in agents}

    # role candidates
    role_candidates: Dict[str, List[Dict[str, Any]]] = {}
    for r in roles:
        top = sorted(
            [{"agent_id": a["id"], "score": scores[a["id"]].get(r, 0.0)} for a in agents],
            key=lambda x: x["score"],
            reverse=True,
        )[:3]
        role_candidates[r] = top

    # agent load
    load: Dict[str, int] = {}
    for r, aid in assigned.items():
        load[aid] = load.get(aid, 0) + 1

    # risks (ochen prostye evristiki)
    risks: List[Dict[str, Any]] = []
    plat_id = assigned.get("platform")
    if plat_id:
        plat = next((a for a in agents if a["id"] == plat_id), None)
        if plat:
            prof = plat.get("profile") or {}
            ft = float(prof.get("flight_time_min") or 0.0)
            lat = float(prof.get("latency_ms") or 0.0)
            if ft < 12.0:
                risks.append({"name": "platform_low_flight", "severity": min(1.0, (12.0 - ft) / 12.0), "reason": f"remaining {ft} min"})
            if lat > 200.0:
                risks.append({"name": "platform_high_latency", "severity": min(1.0, (lat - 200.0) / 800.0), "reason": f"{lat} ms"})

    return jsonify({"ok": True, "team_id": team_id, "role_candidates": role_candidates, "agent_load": load, "risks": risks})


def register(app):
    app.register_blueprint(bp)
    return bp