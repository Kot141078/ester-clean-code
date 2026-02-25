# -*- coding: utf-8 -*-
"""routes/memory_journal_routes_alias.py - REST-alias k zhurnalu sobytiy pamyati Ester.

Zadacha:
  Dat stabilnyy HTTP-vkhod dlya sobytiy “zhurnala opyta”, ne trogaya suschestvuyuschie ruchki.

Ruchki:
  GET /memory/journal/ping
  POST /memory/journal/event {
      "kind": "string",
      "op": "string",
      "ok": true|false,
      "info": {...} # optsionalno, lyubye dop. polya
  }

MOSTY:
  - Yavnyy: (routes ↔ modules.memory.events) - HTTP-sobytiya srazu idut v kanonicheskiy zhurnal.
  - Skrytyy #1: (Kontekst ↔ Memory) — vneshnie agenty i UI pishut v tot zhe potok, chto i vnutrennie moduli.
  - Skrytyy #2: (Memory ↔ QA/summary) — sobytiya avtomaticheski popadayut v sutochnye svodki i proverki kachestva.

ZEMNOY ABZATs:
  Inzhenerno eto “/memory/journal/event” kak normalnyy vkhodnoy log. 
  Kak u lyudey: vse, what s nami proiskhodit i what my delaem, protokoliruetsya v odnom meste, 
  no zdes bez biokhimii - just akkuratnyy strukturirovannyy zhurnal.

# c=a+b"""
from __future__ import annotations

import os
from typing import Any, Dict
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from modules.memory import events
except Exception as e:  # pragma: no cover
    events = None  # type: ignore
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None

bp = Blueprint("memory_journal_routes_alias", __name__, url_prefix="/memory/journal")


def _slot() -> str:
    """A/B-slot dlya bezopasnogo razvertyvaniya.

    ENV:
      ESTER_MEMORY_JOURNAL_AB=A|B, po umolchaniyu A.

    A - osnovnoy put (use modules.memory.events.record_event).
    B - rezervnyy slot (logika sovpadaet, no pomechaet sobytiya kak slot=B)."""
    val = os.environ.get("ESTER_MEMORY_JOURNAL_AB", "A") or "A"
    val = str(val).strip().upper()
    return "B" if val == "B" else "A"


@bp.route("/ping", methods=["GET"])
def ping():
    slot = _slot()
    if _IMPORT_ERROR is not None or events is None:
        return jsonify({
            "ok": False,
            "slot": slot,
            "error": "modules.memory.events_import_failed",
            "details": str(_IMPORT_ERROR),
        }), 500
    return jsonify({"ok": True, "slot": slot, "have_events": hasattr(events, "record_event")})


@bp.route("/event", methods=["POST"])
def add_event():
    """Publichnyy vkhod dlya sobytiy.

    Ne lomaet nichego suschestvuyuschego:
    - format mapitsya na record_event(kind, op, ok=True, info=None)
    - esli events ne importirovan - otvechaem oshibkoy, no ne padaem."""
    slot = _slot()
    if _IMPORT_ERROR is not None or events is None or not hasattr(events, "record_event"):
        return jsonify({
            "ok": False,
            "slot": slot,
            "error": "events_unavailable",
        }), 500

    data = request.get_json(force=True, silent=True) or {}

    kind = str(data.get("kind") or "generic").strip() or "generic"
    op = str(data.get("op") or data.get("operation") or "").strip()
    ok_val = data.get("ok", True)
    ok = bool(ok_val)

    info = data.get("info") or {}
    if not isinstance(info, dict):
        info = {"raw": info}

    # metadata technology for distinguishing A/B and sources
    meta_extra: Dict[str, Any] = {
        "slot": slot,
        "source": str(data.get("source") or "journal_http"),
    }
    meta_extra.update({k: v for k, v in data.items()
                       if k not in ("kind", "op", "operation", "ok", "info")})

    rec = events.record_event(kind=kind, op=op, ok=ok, info={**info, **meta_extra})
    return jsonify({"ok": True, "slot": slot, "event": rec})


def register(app):
    """Bezopasnaya registratsiya blyuprinta.

    Use it like:
        from routes.memory_journal_routes_alias import register
        register(app)

    ili cherez tools/register_memory_journal_alias.py."""
    name = bp.name
    if name not in app.blueprints:
        app.register_blueprint(bp)
    return app