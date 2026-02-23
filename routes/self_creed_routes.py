# -*- coding: utf-8 -*-
"""
routes/self_creed_routes.py - REST API dlya poslaniya «Ottsa» + metriki.

Endpointy:
  • GET  /self/creed          → {"text","meta":{"provenance":...},"tags"}
  • POST /self/creed/affirm   → idempotentno polozhit v pamyat (ili lokalno)
  • GET  /metrics/self_creed  → schetchiki profilea/zapisey/propuskov

Mosty:
- Yavnyy: (Samopoznanie ↔ Memory) izvne i iz voli dostup k tekstu i k ego zapisi v pamyat.
- Skrytyy #1: (Infoteoriya ↔ Audit) profile pomogaet sverit, chto lezhit v pamyati - eto «tot samyy» tekst.
- Skrytyy #2: (UX ↔ Sovmestimost) nikakikh pravok suschestvuyuschikh kontraktov, tolko novye ruchki.

Zemnoy abzats:
Eto dvertsa k «tablichke u serdtsa»: posmotret, podtverdit, chto sokhraneno, i podsmotret metriki.

# c=a+b
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_creed = Blueprint("self_creed", __name__)

try:
    from modules.self.core_creed import creed_object, creed_passport, affirm_to_memory, counters  # type: ignore
except Exception:
    creed_object = creed_passport = affirm_to_memory = counters = None  # type: ignore

def register(app):
    app.register_blueprint(bp_creed)

@bp_creed.route("/self/creed", methods=["GET"])
def api_get_creed():
    if creed_object is None:
        return jsonify({"ok": False, "error": "core_creed module unavailable"}), 500
    obj = creed_object()
    return jsonify({"ok": True, **obj})

@bp_creed.route("/self/creed/affirm", methods=["POST"])
def api_affirm():
    if affirm_to_memory is None:
        return jsonify({"ok": False, "error": "core_creed module unavailable"}), 500
    return jsonify(affirm_to_memory())

@bp_creed.route("/metrics/self_creed", methods=["GET"])
def metrics():
    if counters is None:
        return ("self_creed_passport_built 0\nself_creed_affirm_calls 0\nself_creed_affirm_writes 0\nself_creed_affirm_skips 0\n",
                200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
    c = counters()
    return (f"self_creed_passport_built {c.get('passport_built',0)}\n"
            f"self_creed_affirm_calls {c.get('affirm_calls',0)}\n"
            f"self_creed_affirm_writes {c.get('affirm_writes',0)}\n"
            f"self_creed_affirm_skips {c.get('affirm_skips',0)}\n",
            200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"})
# c=a+b