# -*- coding: utf-8 -*-
"""
Vspomogatelnyy i bezopasnyy API k pamyati (na sluchay, esli starye routy esche gde-to lomayutsya).

Endpointy:
  POST /mem_boot/remember    {text, role?, tags?, meta?}
  GET  /mem_boot/qa?q=...
  POST /mem_boot/daily_cycle

Mosty:
- Yavnyy: Memory ↔ Vneshniy mir - mozhno klast i chitat pamyat bez bolshikh zavisimostey.
- Skrytyy 1: Diagnostika ↔ Operatsii - bystryy smoke-interfeys, poka privodim osnovnye routy v poryadok.
- Skrytyy 2: UI/Health ↔ Nadezhnost - izolirovannyy blyuprint, ne konfliktuet s suschestvuyuschimi.

Zemnoy abzats:
Eto servisnaya dvertsa: dazhe esli «paradnyy vkhod» pamyati esche v remonte, cherez etu dvertsu mozhno zanosit i dostavat zapisi.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import remember as mem_remember, qa as mem_qa, daily_cycle as mem_daily
except Exception:
    # lenivyy import cherez lokalnyy put, chtoby ne upast voobsche
    from modules.memory.api import remember as mem_remember, qa as mem_qa, daily_cycle as mem_daily  # type: ignore

bp = Blueprint("mem_boot_routes", __name__, url_prefix="/mem_boot")

@bp.post("/remember")
def _remember():
    data = request.get_json(silent=True) or {}
    res = mem_remember({
        "text": data.get("text", ""),
        "role": data.get("role", "user"),
        "tags": data.get("tags", []),
        "meta": data.get("meta", {}),
    })
    return jsonify({"ok": True, "event": res})

@bp.get("/qa")
def _qa():
    q = request.args.get("q", "") or (request.get_json(silent=True) or {}).get("q", "")
    res = mem_qa(q)
    return jsonify(res)

@bp.post("/daily_cycle")
def _daily():
    res = mem_daily()
    return jsonify(res)

# Sovmestimost s register_all: podderzhivaem i obekt bp, i funktsiyu register(app).
def register(app):
    app.register_blueprint(bp)
    return "mem_boot_routes"

# c=a+b