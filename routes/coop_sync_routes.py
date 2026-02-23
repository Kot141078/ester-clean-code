# -*- coding: utf-8 -*-
"""
Cooperative room sync routes.

Examples:
  POST /coop/join   {"room":"demo","peer_id":"A","name":"Node-PC"}
  POST /coop/leave  {"room":"demo","peer_id":"A"}
  POST /coop/event  {"room":"demo","peer_id":"A","type":"hotkey","payload":{"keys":"WIN+R"}}
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from modules.coop.room import (
    broadcast,
    join,
    leave,
    pull,
    rotate_leader,
    set_leader,
    set_quota,
    status,
    tick,
)

bp = Blueprint("coop_sync_routes", __name__, url_prefix="/coop")


@bp.route("/join", methods=["POST"])
def r_join():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(join(str(d.get("room", "default")), str(d.get("peer_id", "peer")), str(d.get("name", ""))))


@bp.route("/leave", methods=["POST"])
def r_leave():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(leave(str(d.get("room", "default")), str(d.get("peer_id", "peer"))))


@bp.route("/leader/set", methods=["POST"])
def r_set_leader():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(set_leader(str(d.get("room", "default")), str(d.get("peer_id", "peer"))))


@bp.route("/leader/rotate", methods=["POST"])
def r_rotate():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(rotate_leader(str(d.get("room", "default"))))


@bp.route("/quota", methods=["POST"])
def r_quota():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(set_quota(str(d.get("room", "default")), d.get("tick_hz"), d.get("aps")))


@bp.route("/event", methods=["POST"])
def r_event():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(
        broadcast(
            str(d.get("room", "default")),
            str(d.get("peer_id", "peer")),
            str(d.get("type", "")),
            dict(d.get("payload") or {}),
        )
    )


@bp.route("/tick", methods=["POST"])
def r_tick():
    d = request.get_json(force=True, silent=True) or {}
    return jsonify(tick(str(d.get("room", "default")), int(d.get("n", 1))))


@bp.route("/pull", methods=["GET"])
def r_pull():
    room = str(request.args.get("room", "default"))
    since = int(request.args.get("since", 0))
    limit = int(request.args.get("limit", 200))
    return jsonify(pull(room, since, limit))


@bp.route("/status", methods=["GET"])
def r_status():
    room = str(request.args.get("room", "default"))
    return jsonify(status(room))


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_coop.html")


def register(app):
    app.register_blueprint(bp)
