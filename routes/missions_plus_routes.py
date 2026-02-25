# -*- coding: utf-8 -*-
"""routes/missions_plus_routes.py - REST/UI dlya dolgikh missiy.

Ruchki:
  GET /thinking/missions/list
  POST /thinking/missions/create {"goal":"...", "priority":"low|normal|high", "schedule":"@daily 04:20", "template":"cascade|pipeline", "params":{...}}
  POST /thinking/missions/update {"id":"...", ...patch}
  POST /thinking/missions/pause {"id":"..."}
  POST /thinking/missions/resume {"id":"..."}
  POST /thinking/missions/cancel {"id":"..."}
  POST /thinking/missions/finalize {"id":"...","note":"..."}
  POST /thinking/missions/start_scheduler
  POST /thinking/missions/stop_scheduler
  GET /thinking/missions/status
  GET /admin/missions_plus (alias k /thinking/missions/admin)

Mosty:
- Yavnyy: (Planirovschik ↔ Myslitelnyy kontur) REST-upravlenie zhiznennym tsiklom missiy.
- Skrytyy #1: (Logika ↔ Kontrakty) determinirovannye JSON-otvety/kody oshibok.
- Skrytyy #2: (Memory ↔ Audit) legko add zhurnal v “profile”.
- Skrytyy #3: (Kibernetika ↔ Obratnaya svyaz) finalize/ pause/ resume zamykayut tsikl.

Zemnoy abzats:
Eto kak dispetcher poletov: sozdaem reys (missiyu), stavim raspisanie, priostanavlivaem/prodlevaem,
i v kontse fiksiruem posadku (finalize). All prozrachno i predskazuemo.

# c=a+b"""
from __future__ import annotations

from typing import Any, Dict

from flask import Blueprint, jsonify, request, render_template
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("missions_plus_routes", __name__, url_prefix="/thinking/missions")

# Soft import of a thought engine
try:
    from modules.thinking import missions as MS  # type: ignore
except Exception:  # pragma: no cover
    MS = None  # type: ignore


def _require_ms():
    if MS is None:
        return jsonify({"ok": False, "error": "missions module unavailable"}), 500
    return None


@bp.get("/list")
def list_():
    err = _require_ms()
    if err:
        return err
    try:
        return jsonify(MS.list_())  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/create")
def create():
    err = _require_ms()
    if err:
        return err
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    goal = (d.get("goal") or "").strip()
    if not goal:
        return jsonify({"ok": False, "error": "goal required"}), 400
    priority = (d.get("priority") or "normal").lower()
    if priority not in {"low", "normal", "high"}:
        return jsonify({"ok": False, "error": "priority must be low|normal|high"}), 400
    schedule = str(d.get("schedule") or "")
    template = str(d.get("template") or "cascade")
    params = d.get("params") or {}
    try:
        return jsonify(MS.create(goal, priority, schedule, template, params))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/update")
def update():
    err = _require_ms()
    if err:
        return err
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    mid = (d.get("id") or "").strip()
    if not mid:
        return jsonify({"ok": False, "error": "id required"}), 400
    try:
        return jsonify(MS.update(mid, d))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/pause")
def pause():
    err = _require_ms()
    if err:
        return err
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    mid = (d.get("id") or "").strip()
    if not mid:
        return jsonify({"ok": False, "error": "id required"}), 400
    try:
        return jsonify(MS.pause(mid))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/resume")
def resume():
    err = _require_ms()
    if err:
        return err
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    mid = (d.get("id") or "").strip()
    if not mid:
        return jsonify({"ok": False, "error": "id required"}), 400
    try:
        return jsonify(MS.resume(mid))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/cancel")
def cancel():
    err = _require_ms()
    if err:
        return err
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    mid = (d.get("id") or "").strip()
    if not mid:
        return jsonify({"ok": False, "error": "id required"}), 400
    try:
        return jsonify(MS.cancel(mid))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/finalize")
def finalize():
    err = _require_ms()
    if err:
        return err
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    mid = (d.get("id") or "").strip()
    if not mid:
        return jsonify({"ok": False, "error": "id required"}), 400
    note = str(d.get("note") or "")
    try:
        return jsonify(MS.finalize(mid, note))  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/start_scheduler")
def start_scheduler():
    err = _require_ms()
    if err:
        return err
    try:
        return jsonify(MS.start())  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/stop_scheduler")
def stop_scheduler():
    err = _require_ms()
    if err:
        return err
    try:
        return jsonify(MS.stop())  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/status")
def status():
    err = _require_ms()
    if err:
        return err
    try:
        return jsonify(MS.status())  # type: ignore[attr-defined]
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/admin")
def admin():
    return render_template("admin_missions_plus.html")


def register(app):  # pragma: no cover
    """Drop-in registration of blueprint and aliases (project contract)."""
    app.register_blueprint(bp)
    # Alias ​​for admin under the “old” path
    app.add_url_rule("/admin/missions_plus", view_func=admin, methods=["GET"], endpoint="admin_missions_plus_alias")


def init_app(app):  # pragma: no cover
    """Compatible initialization hook (pattern from dump)."""
    register(app)


__all__ = ["bp", "register", "init_app"]
# c=a+b