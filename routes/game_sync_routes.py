# -*- coding: utf-8 -*-
"""
routes/game_sync_routes.py - REST/UI dlya «sovmestnoy igry».

Ruchki:
  POST /game/config {"tick_rate":20,"peers":["..."],"quota":5,"room":"test"}
  POST /game/start  {}
  POST /game/stop   {}
  POST /game/ingest {"peer":"p1","action":{"kind":"input","type":"hotkey","seq":"CTRL+S"}}
  GET  /game/status
  GET  /admin/game

# c=a+b
"""
from __future__ import annotations

from typing import Any, Dict, List

from flask import Blueprint, jsonify, request, render_template

# Drop-in: sokhranyaem kontrakty moduley
from modules.coop.game_sync import configure, start, stop, ingest_action, status  # type: ignore
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("game_sync_routes", __name__, url_prefix="/game")


@bp.route("/config", methods=["POST"])
def cfg():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    try:
        tick_rate = int(d.get("tick_rate", 20))
        quota = int(d.get("quota", 5))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "tick_rate/quota must be integers"}), 400
    peers_in = d.get("peers") or []
    peers: List[str] = list(peers_in) if isinstance(peers_in, (list, tuple)) else [str(peers_in)]
    room = d.get("room")
    try:
        return jsonify(configure(tick_rate, peers, quota, room))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/start", methods=["POST"])
def st():
    try:
        return jsonify(start())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/stop", methods=["POST"])
def sp():
    try:
        return jsonify(stop())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/ingest", methods=["POST"])
def ing():
    d: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    peer = str(d.get("peer", "anon"))
    action: Dict[str, Any] = d.get("action") or {}
    try:
        return jsonify(ingest_action(peer, action))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/status", methods=["GET"])
def s():
    try:
        return jsonify(status())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_game.html")


def register(app):  # pragma: no cover
    """Drop-in registratsiya blyuprinta (kontrakt proekta)."""
    app.register_blueprint(bp)


def init_app(app):  # pragma: no cover
    """Sovmestimyy khuk initsializatsii (pattern iz dampa)."""
    register(app)


__all__ = ["bp", "register", "init_app"]