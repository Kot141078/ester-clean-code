# -*- coding: utf-8 -*-
"""routes/sos_routes.py - offlayn SOS i prostye REST-triggery.

Mosty:
- Yavnyy: (Bezopasnost zhizni ↔ Offlayn) vydaem nomera i shpargalku bez seti.
- Skrytyy #1: (Profile ↔ Audit) pishem vyzovy v lokalnyy zhurnal data/sos_log.jsonl.
- Skrytyy #2: (RBAC ↔ Prozrachnost) optsionalnyy JWT i yasnye kody oshibok.

Zemnoy abzats:
Like pamyatka u telefona: “112 / 103 / 101.” Pod rukoy i bez internetov.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict, List
import json, os, time

from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask_jwt_extended import jwt_required  # type: ignore
except Exception:
    def jwt_required(*args, **kwargs):  # type: ignore
        def _wrap(fn): return fn
        return _wrap

bp_sos = Blueprint("sos_routes", __name__)

CARDS: Dict[str, Dict[str, Any]] = {
    "EU": {"emergency": "112", "notes": ["Nazovite adres/sostoyanie", "Ostavaytes na linii"]},
    "BE": {"emergency": "112", "medical": "112", "fire": "112", "police": "112", "notes": ["FR/NL/DE/EN dostupny"]},
    "RU": {"emergency": "112", "ambulance": "103", "police": "102", "fire": "101", "notes": ["Tell us the city/street/entrance"]},
    "US": {"emergency": "911", "notes": ["State your location", "Describe the emergency", "Stay on the line"]},
    "UA": {"emergency": "112", "ambulance": "103", "police": "102", "fire": "101", "notes": ["Vkazhіt adresu/orієntiri"]},
}

def _log(kind: str, payload: Dict[str, Any]) -> None:
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/sos_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "kind": kind, "payload": payload}, ensure_ascii=False) + "\n")
    except Exception:
        pass

@bp_sos.get("/aid/cards")
@jwt_required(optional=True)
def aid_cards():
    return jsonify({"ok": True, "cards": CARDS})

@bp_sos.post("/aid/quickcall")
@jwt_required(optional=True)
def quickcall():
    d: Dict[str, Any] = request.get_json(True, True) or {}
    country = str(d.get("country", "EU")).upper()
    purpose = str(d.get("purpose", "medical")).lower()
    address = d.get("address")
    card = CARDS.get(country, CARDS["EU"])
    number = str(card.get(purpose) or card.get("emergency", "112"))
    script: List[str] = ["Pozvonit: " + number] + list(card.get("notes") or [])
    if address:
        script.insert(1, f"Adres: {address}")
    rec = {"country": country, "purpose": purpose, "address": address, "number": number, "script": script}
    _log("quickcall", rec)
    return jsonify({"ok": True, **rec})

def register(app) -> None:
    if bp_sos.name in getattr(app, "blueprints", {}):
        return
    app.register_blueprint(bp_sos)


def register(app):
    app.register_blueprint(bp_sos)
    return app