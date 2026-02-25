# -*- coding: utf-8 -*-
"""routes/ester_status_routes_alias.py - HTTP-dostup k statusu rezhimov Ester.

Mosty:
- Yavnyy: (HTTP ↔ modules.ester.status) - vydaet status kaskada/voli/trace.
- Skrytyy #1: (DevOps ↔ Arkhitektura) — pozvolyaet monitorit rezhimy bez lezviya v kod.
- Skrytyy #2: (Chelovek ↔ Subekt Ester) — pokazyvaet, v kakom "nastroenii" ona myslit.

Invariance:
- Just read. Nikakikh pereklyucheniy rezhimov cherez etot rout.
- Prefiks /ester/status - ne konfliktuet s tekuschimi osnovnymi routes.

Zemnoy abzats:
curl http://host:port/ester/status - i vidno, kak nastroena golova Ester.
# c=a+b"""
from __future__ import annotations

from typing import Any
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask import Blueprint, jsonify
except Exception:  # pragma: no cover
    Blueprint = None  # type: ignore
    jsonify = None    # type: ignore

try:
    from modules.ester.status import get_status, get_human_summary
except Exception:  # pragma: no cover
    get_status = None  # type: ignore
    get_human_summary = None  # type: ignore


def create_blueprint():
    if Blueprint is None or jsonify is None or get_status is None:
        return None

    bp = Blueprint("ester_status_bp", __name__, url_prefix="/ester")

    @bp.route("/status", methods=["GET"])
    def status() -> Any:  # pragma: no cover
        st = get_status()
        return jsonify({"ok": True, "status": st, "summary": get_human_summary()})

    @bp.route("/modes", methods=["GET"])
    def modes() -> Any:  # pragma: no cover
        st = get_status()
        return jsonify(st)

    return bp