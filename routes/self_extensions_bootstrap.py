# -*- coding: utf-8 -*-
"""routes/self_extensions_bootstrap.py - drop-in “butstrap”: podkhvatit vse rasshirniya pri registratsii blyuprinta.

Effect:
  • Pri starte prilozheniya (avtoregistratsiya blyuprintov) vyzovem dynamic_loader.load_all(app).

Mosty:
- Yavnyy: (Inzheneriya ↔ Sovmestimost) ne trogaem app.py - rashirniya podklyuchatsya sami.
- Skrytyy #1: (Kibernetika ↔ Kontrol) oshibki zagruzki ne valyat server; log visible v otvete /self/capabilities.
- Skrytyy #2: (Infoteoriya ↔ Audit) sokhranyaetsya predskazuemost putey i registriruemykh moduley.

Zemnoy abzats:
Eto tikhiy “zvonok elektrika”: pri zapuske proyti i akkuratno vklyuchit vse novye moduli.

# c=a+b"""
from __future__ import annotations

from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp_self_boot = Blueprint("self_ext_bootstrap", __name__)

try:
    from modules.self.dynamic_loader import load_all  # type: ignore
except Exception:
    load_all = None  # type: ignore

def register(app):
    app.register_blueprint(bp_self_boot)
    if load_all:
        # launch the utility upon registration
        app.config["SELF_EXT_LOAD_RESULT"] = load_all(app)

@bp_self_boot.route("/self/extensions/load_result", methods=["GET"])
def load_result():
    rep = {"ok": True}
    try:
        from flask import current_app
        rep["result"] = current_app.config.get("SELF_EXT_LOAD_RESULT", {})
    except Exception:
        rep["result"] = {}
    return jsonify(rep)