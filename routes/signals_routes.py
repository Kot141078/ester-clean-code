# -*- coding: utf-8 -*-
"""
routes/signals_routes.py - UI/REST dlya indikatsiy sostoyaniya (fizicheskikh i virtualnykh).

Mosty:
- Yavnyy: (HTTP UI ↔ PhysIO) - knopki v adminke otdayut impulsy v modul signalov.
- Skrytyy 1: (Diagnostika ↔ Memory) - zhurnal sobytiy dostupen REST'om, prigoden dlya korrelyatsii intsidentov.
- Skrytyy 2: (Bezopasnost ↔ UX) - A/B-slot otobrazhaetsya v UI, chtoby vklyuchat «smelyy» rezhim osoznanno.

Zemnoy abzats:
Stranichka s tremya knopkami - «info», «vnimanie», «oshibka». Nazhal - Ester podala znak i zapisala v zhurnal.
Polezno, kogda ekran daleko: slyshno/vidno, chto ona zhiva i reagiruet.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request, render_template

from modules.physio.io_signals import pulse, read_state
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("signals_routes", __name__, url_prefix="/signals")


@bp.route("/pulse", methods=["POST"])
def route_pulse():
    data = request.get_json(force=True, silent=True) or {}
    level = str(data.get("level", "info"))
    ttl_ms = int(data.get("ttl_ms", 500))
    return jsonify(pulse(level=level, ttl_ms=ttl_ms))


@bp.route("/state", methods=["GET"])
def route_state():
    limit = int(request.args.get("limit", 50))
    return jsonify(read_state(limit=limit))


@bp.route("/admin", methods=["GET"])
def admin():
    return render_template("admin_signals.html")


def register(app):
    app.register_blueprint(bp)


# finalnaya stroka
# c=a+b