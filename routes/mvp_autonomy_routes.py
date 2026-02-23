# routes/mvp_autonomy_routes.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import Blueprint, current_app, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

BP = Blueprint("mvp_autonomy", __name__)

_STATE: Dict[str, Any] = {
    "ticks": 0,
    "last_tick_at": None,
    "history": [],  # last N
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _call(path: str, method: str = "GET", json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with current_app.test_client() as c:
        if method == "POST":
            r = c.post(path, json=json_body or {})
        else:
            r = c.get(path)
        return (r.get_json(silent=True) or {"status": r.status_code})


@BP.get("/mvp/autonomy/status")
def status():
    return jsonify(
        {
            "ok": True,
            "ticks": _STATE["ticks"],
            "last_tick_at": _STATE["last_tick_at"],
            "history_len": len(_STATE["history"]),
        }
    )


@BP.post("/mvp/autonomy/tick")
def tick():
    body = request.get_json(silent=True) or {}
    execute = bool(body.get("execute", False))
    confirm = bool(body.get("confirm", False))

    # safe-by-default: execute requires explicit confirm
    if execute and not confirm:
        execute = False

    # minimal “own needs” (smoke-friendly)
    tasks: List[str] = body.get("tasks") if isinstance(body.get("tasks"), list) else [
        "U menya oshibki i vse tormozit, prover health/metrics",
        "Naydi po baze dokument pro RBAC i protsitiruy",
        "Mne nuzhen novyy agent: YAML + geyty, sdelay chernovik",
    ]

    plan: List[Dict[str, Any]] = []
    for t in tasks:
        advice = _call("/synergy/assign/advice", method="POST", json_body={"task": t})
        agent_id = (advice.get("recommend") or {}).get("agent_id")

        item: Dict[str, Any] = {"task": t, "advice": advice, "executed": False}
        if execute and agent_id:
            # run through suite
            run = _call("/mvp/agents/suite/run", method="POST", json_body={"agent_id": agent_id, "input": {"text": t}, "dry_run": True})
            item["executed"] = True
            item["result"] = run
        plan.append(item)

    _STATE["ticks"] += 1
    _STATE["last_tick_at"] = _now_iso()
    _STATE["history"] = (plan + _STATE["history"])[:20]

    return jsonify({"ok": True, "execute": execute, "confirmed": bool(confirm), "plan": plan})


def register(app):
    app.register_blueprint(BP)
    return True