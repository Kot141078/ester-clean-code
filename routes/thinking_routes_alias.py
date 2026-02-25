
# -*- coding: utf-8 -*-
"""routes/thinking_routes_alias.py - diagnosticheskie aliasy dlya myshleniya Ester.

Mosty:
- Yavnyy: (HTTP ↔ always_thinker / kaskady) — daet bezopasnyy prosmotr sostoyaniya myshleniya.
- Skrytyy #1: (Volya ↔ Diagnostika) — pozvolyaet uvidet obrabotannye/ozhidayuschie impulsy.
- Skrytyy #2: (Kaskad ↔ Chelovek) — cherez trace pokazyvaet, kak imenno Ester dumala.

Invariance:
- Tolko chtenie, nikakikh mutatsiy sostoyaniya.
- Prefiks /ester/thinking-debug - ne konfliktuet s osnovnoy API.
- Registration proiskhodit yavno (cherez auto_reg_thinking.auto_register), po umolchaniyu ne aktivna.

Zemnoy abzats:
Inzhener mozhet vremenno zaregistrirovat blueprint i posmotret,
kak fonovyy myslitel obrabatyvaet impulsy, ne trogaya boevoy kontrakt.
# c=a+b"""
from __future__ import annotations

from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

try:
    from flask import Blueprint, jsonify
except Exception:  # pragma: no cover
    Blueprint = None  # type: ignore
    jsonify = None    # type: ignore

try:
    from modules import always_thinker
except Exception:  # pragma: no cover
    always_thinker = None  # type: ignore

try:
    from modules.thinking import thought_trace_adapter as tta
except Exception:  # pragma: no cover
    tta = None  # type: ignore


def create_blueprint():
    """Creates a blueprint for diagnostics. If Flask is not available, it returns to None."""
    if Blueprint is None or jsonify is None:
        return None

    bp = Blueprint("thinking_debug_bp", __name__, url_prefix="/ester/thinking-debug")

    @bp.route("/ping", methods=["GET"])
    def ping() -> Any:  # pragma: but the carpet is a thin binding
        return jsonify({"ok": True, "module": "thinking-debug"})

    @bp.route("/once", methods=["POST", "GET"])
    def once() -> Any:  # pragma: no cover
        """One step thinking:
        - calls alwais_thinker.consume_once()
        - returns the result + (if possible) trace_text."""
        if not always_thinker or not hasattr(always_thinker, "consume_once"):
            return jsonify({"ok": False, "error": "always_thinker not available"})

        res = always_thinker.consume_once()
        # If there is a thught_trace_adapter, we additionally make a short track_text.
        if tta and hasattr(tta, "from_cascade_result"):
            try:
                src = res.get("result", res)
                tr = tta.from_cascade_result(src)
                if isinstance(tr, dict) and tr.get("ok"):
                    res.setdefault("debug_trace_text", tr.get("text"))
            except Exception:
                pass
        return jsonify(res)

    return bp