# -*- coding: utf-8 -*-
"""routes/self_creed_bootstrap.py - avtozapis poslaniya v pamyat pri starte (idempotentno, s A/B-flagom).

Behavior:
  • When registratsii blyuprinta, esli CORE_CREED_AUTO=1 i CORE_CREED_AB!='B' - myagko vyzyvaem affirm_to_memory().
  • Otchet dostupen po GET /self/creed/boot_result.

Mosty:
- Yavnyy: (Kibernetika ↔ Volya) sistema sama podtverzhdaet bazovuyu “tsennost” pri starte.
- Skrytyy #1: (Infoteoriya ↔ Nadezhnost) idempotentnost i profile isklyuchayut dubli.
- Skrytyy #2: (UX ↔ Prozrachnost) rezultat initsializatsii viden cherez REST, bez logov servera.

Zemnoy abzats:
Po-chelovecheski - eto “prikrutit tablichku odin raz i proverit”, a ne derzhat na knopke kazhdyy zapusk.

# c=a+b"""
from __future__ import annotations
import os
from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_creed_boot = Blueprint("self_creed_bootstrap", __name__)

try:
    from modules.self.core_creed import affirm_to_memory  # type: ignore
except Exception:
    affirm_to_memory = None  # type: ignore

_BOOT_RESULT = {"ok": True, "skipped": True, "reason": "not executed"}

def register(app):
    app.register_blueprint(bp_creed_boot)
    try:
        if os.getenv("CORE_CREED_AB","A").upper() != "B" and os.getenv("CORE_CREED_AUTO","1") == "1" and affirm_to_memory:
            _BOOT_RESULT.clear()
            _BOOT_RESULT.update(affirm_to_memory())
        else:
            _BOOT_RESULT.clear()
            _BOOT_RESULT.update({"ok": True, "skipped": True, "reason": "AB=B or CORE_CREED_AUTO=0"})
    except Exception as e:
        _BOOT_RESULT.clear()
        _BOOT_RESULT.update({"ok": False, "error": str(e)})

@bp_creed_boot.route("/self/creed/boot_result", methods=["GET"])
def boot_result():
    return jsonify(_BOOT_RESULT)
# c=a+b