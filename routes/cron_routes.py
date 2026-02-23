# -*- coding: utf-8 -*-
"""
routes/cron_routes.py - REST for scheduler control and on-demand runs. ASCII-only docstring.

Bridges:
- Explicit: Web <-> Timer (control via /cron/*).
- Hidden #1: Control <-> Transparency (passport-friendly JSON results).
- Hidden #2: Distributed <-> Reliability (optional P2P task sync).

Ground paragraph:
Think of it as an alarm panel: list tasks/jobs, start/stop, seed, run now, tick,
basic P2P sync, and a background monitor loop. No external I/O required to work.

c=a+b
"""
from __future__ import annotations

import os
import json
import time
import base64
import socket
import threading
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Optional HTTP client
try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore[assignment]

bp = Blueprint("cron_routes", __name__)

# Settings
P2P_PEERS = [p for p in (os.getenv("ESTER_P2P_PEERS") or "").split(",") if p.strip()]
CLOUD_ENDPOINT = os.getenv("CLOUD_ENDPOINT", "https://example.invalid/analyze")
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
FAILURES_ALERT_THRESHOLD = int(os.getenv("CRON_ALERT_FAILS", "5") or "5")

# Optional scheduler API
try:
    from modules.cron.scheduler import (  # type: ignore
        start,
        stop,
        seed_default,
        status as _status,
        list_tasks,
        list_jobs,
        add_task as _upsert,
        run_now as _run_one,
        tick as _tick,
    )
except Exception:
    start = stop = seed_default = _status = list_tasks = list_jobs = _upsert = _run_one = _tick = None  # type: ignore


def register(app):
    """Idempotent blueprint registration and background monitor launch."""
    if "cron_routes" in app.blueprints:
        return app
    app.register_blueprint(bp)
    # Best-effort start and seed
    try:
        if start:
            start()
        if list_tasks and seed_default:
            items = {}
            try:
                items = list_tasks() or {}
            except Exception:
                items = {}
            if not (items.get("items") or []):
                try:
                    seed_default()
                except Exception:
                    pass
    except Exception:
        pass
    # Background monitor
    try:
        threading.Thread(target=_background_monitor, daemon=True).start()
    except Exception:
        pass
    return app


def _passport(event: str, data: Dict[str, Any]) -> None:
    """Best-effort log to passport, if available."""
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp(event, data, "cron://api")
    except Exception:
        pass


def _enc(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("utf-8")


def _dec(s: str) -> str:
    return base64.b64decode(s.encode("utf-8")).decode("utf-8")


def _p2p_sync(payload: Dict[str, Any]) -> None:
    if not P2P_PEERS:
        return
    try:
        data = _enc(json.dumps(payload))
    except Exception:
        data = ""
    for peer in P2P_PEERS:
        try:
            host, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect((host, int(port)))
                sock.sendall(f"SYNC_CRON:{data}".encode("utf-8"))
        except Exception:
            continue


def _judge_alert(metrics: Dict[str, Any]) -> None:
    try:
        failures = int(metrics.get("failures", 0))
    except Exception:
        failures = 0
    if failures <= FAILURES_ALERT_THRESHOLD:
        return
    if not CLOUD_API_KEY or not requests:
        return
    try:
        requests.post(  # type: ignore[union-attr]
            CLOUD_ENDPOINT,
            json={"metrics": metrics, "key": CLOUD_API_KEY},
            timeout=5,
        )
    except Exception:
        pass


def _background_monitor() -> None:
    while True:
        try:
            if _tick:
                _tick()
            if _status:
                rep = _status()
                _judge_alert(rep if isinstance(rep, dict) else {})
        except Exception:
            pass
        time.sleep(60)


@bp.route("/cron/status", methods=["GET"])
def api_status():
    if _status is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = _status()
        _judge_alert(rep if isinstance(rep, dict) else {})
        _passport("cron_status", {"running": bool(getattr(rep, "get", lambda *_: False)("running"))})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/cron/list", methods=["GET"])
def api_list():
    if list_tasks is None or list_jobs is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        tasks = (list_tasks() or {}).get("items", [])
    except Exception:
        tasks = []
    try:
        jobs = (list_jobs() or {}).get("jobs", [])
    except Exception:
        jobs = []
    _passport("cron_list", {"tasks": len(tasks), "jobs": len(jobs)})
    return jsonify({"ok": True, "tasks": tasks, "jobs": jobs})


@bp.route("/cron/plan", methods=["POST"])
def api_plan():
    if seed_default is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = seed_default()
        _p2p_sync(rep if isinstance(rep, dict) else {})
        _passport("cron_plan", {"seeded": True})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/cron/task/upsert", methods=["POST"])
def api_upsert_task():
    if _upsert is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _dec(v) if isinstance(v, str) else v for k, v in d_enc.items()}
    try:
        rep = _upsert(d.get("name"), rrule=d.get("rrule"), cron=d.get("cron"), action=d.get("action"))  # type: ignore[misc]
        _p2p_sync(rep if isinstance(rep, dict) else {})
        _passport("cron_upsert", {"name": d.get("name")})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


def _run_one_safe(name: str, **kw) -> Dict[str, Any]:
    if _run_one is None:
        return {"ok": False, "error": "cron_unavailable"}
    try:
        return _run_one(name, **kw)  # type: ignore[misc]
    except TypeError:
        return _run_one(name)  # type: ignore[misc]


@bp.route("/cron/run", methods=["POST"])
def api_run():
    if _run_one is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _dec(v) if isinstance(v, str) else v for k, v in d_enc.items()}
    name = str(d.get("name") or "")
    rep = _run_one_safe(name)
    _passport("cron_run", {"name": name})
    return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})


@bp.route("/cron/nightly/run", methods=["POST"])
def api_run_nightly():
    if _run_one is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    dry_run = bool(d.get("dry_run", False))
    rep = _run_one_safe("nightly", dry_run=dry_run)
    _passport("cron_nightly_run", {"dry_run": dry_run})
    return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})


@bp.route("/cron/jobs/run", methods=["POST"])
def api_run_jobs():
    if _run_one is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    d = request.get_json(force=True, silent=True) or {}
    ids = d.get("ids") or []
    if not isinstance(ids, list):
        return jsonify({"ok": False, "error": "invalid_input"}), 400
    results: Dict[str, Any] = {}
    for i in ids:
        results[str(i)] = _run_one_safe(str(i))
    _passport("cron_jobs_run", {"count": len(ids)})
    return jsonify({"ok": True, "results": results})


@bp.route("/cron/tick", methods=["POST"])
def api_tick():
    if _tick is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = _tick()
        _passport("cron_tick", {})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/cron/start", methods=["POST"])
def api_start():
    if start is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = start()
        _passport("cron_start", {})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/cron/stop", methods=["POST"])
def api_stop():
    if stop is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = stop()
        _passport("cron_stop", {})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/cron/seed_default", methods=["POST"])
def api_seed():
    if seed_default is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = seed_default()
        _p2p_sync(rep if isinstance(rep, dict) else {})
        _passport("cron_seed_default", {})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@bp.route("/cron/config", methods=["POST"])
def api_config():
    if _upsert is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    d_enc = request.get_json(force=True, silent=True) or {}
    d = {k: _dec(v) if isinstance(v, str) else v for k, v in d_enc.items()}
    enable = d.get("enable")
    time_str = d.get("time")
    tz = d.get("tz")

    cron: Optional[str] = None
    if isinstance(time_str, str) and ":" in time_str:
        hh, mm = time_str.split(":", 1)
        cron = f"0 {int(mm)} {int(hh)} * * *"

    try:
        rep = _upsert("nightly", cron=cron, action="run_nightly")  # type: ignore[misc]
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

    # Optional start/stop
    try:
        if enable is True and start:
            start()
        if enable is False and stop:
            stop()
    except Exception:
        pass

    _p2p_sync(rep if isinstance(rep, dict) else {})
    _passport("cron_config", {"enable": enable, "time": time_str, "tz": tz})
    return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})


@bp.route("/cron/monitor", methods=["GET"])
def api_monitor():
    if _status is None:
        return jsonify({"ok": False, "error": "cron_unavailable"}), 500
    try:
        rep = _status()
        _judge_alert(rep if isinstance(rep, dict) else {})
        _passport("cron_monitor", {})
        return jsonify(rep if isinstance(rep, dict) else {"ok": True, "result": rep})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500
# c=a+b