# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required  # type: ignore

bp_p2p_tasks = Blueprint("p2p_tasks", __name__)

# Ispolzuem imeyuschiysya sink-dvizhok
from scheduler.sync_job import sync_once  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _schedule_sync(rrule: str) -> Dict[str, Any]:
    """
    Pytaemsya sozdat periodicheskuyu zadachu sinkhronizatsii cherez tvoy planirovschik.
    Sovmestimo s Iteration B API:
      create_task(kind, action, rrule, payload) -> dict
    """
    try:
        from modules.scheduler_engine import create_task  # type: ignore
    except Exception:
        return {"ok": False, "err": "scheduler_unavailable"}

    payload = {"kind": "p2p.sync", "note": "auto CRDT/Merkle sync"}
    try:
        r = create_task(kind="p2p.sync", action="p2p.sync.run", rrule=rrule, payload=payload)
        return {"ok": True, "task": r}
    except Exception as e:
        return {"ok": False, "err": str(e)}


@bp_p2p_tasks.post("/p2p/sync/run")
@jwt_required()  # lokalno — trebuem avtorizatsiyu
def p2p_sync_run():
    res = sync_once()
    return jsonify({"ok": True, "result": res})


@bp_p2p_tasks.post("/p2p/sync/schedule")
@jwt_required()
def p2p_sync_schedule():
    """
    Telo: {"rrule": "FREQ=MINUTELY;INTERVAL=1"} ili cron-podobnaya stroka, esli tak realizovano v tvoem planirovschike.
    """
    data = request.get_json(force=True, silent=True) or {}
    rrule = str(data.get("rrule") or "FREQ=MINUTELY;INTERVAL=1")
    r = _schedule_sync(rrule)
    code = 200 if r.get("ok") else 503
    return jsonify(r), code


def register(app):
    app.register_blueprint(bp_p2p_tasks)
    return app
