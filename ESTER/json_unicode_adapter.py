"""
Ester JSON unicode adapter.

Pozvolyaet upravlyat rezhimom serializatsii JSON dlya HTTP-otvetov Flask.

AB-pereklyuchatel:
- A (po umolchaniyu): povedenie Flask po umolchaniyu (escape ASCII), nichego ne trogaem.
- B: otklyuchaem ASCII-ekranirovanie dlya JSON-otvetov (JSON_AS_ASCII=False),
     chtoby kirillitsa i drugie unicode-simvoly otobrazhalis normalno.

Ispolzovanie:
- app.py pytaetsya importirovat etot modul i vyzvat apply(app).
- Esli adapter nedostupen ili chto-to poshlo ne tak — Ester prodolzhit rabotat v bezopasnom rezhime.
"""

import os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_FLAG = "ESTER_JSON_UNICODE_AB"


def apply(app) -> Dict[str, Any]:
    """
    Primenit nastroyki JSON unicode k Flask-prilozheniyu.

    Vozvraschaet slovar:
      {"ok": bool, "mode": "A"|"B", "changed": bool, ...}
    """
    try:
        mode = (os.getenv(_FLAG, "A") or "A").strip().upper()
    except Exception:
        # maksimalno bezopasno: esli chto-to strannoe v okruzhenii — ne lomaemsya
        mode = "A"

    if mode != "B":
        # Nichego ne menyaem — povedenie po umolchaniyu.
        return {"ok": True, "mode": "A", "changed": False}

    # Pytaemsya akkuratno vklyuchit unicode v JSON.
    changed = False
    try:
        # Sovmestimyy dlya Flask 2/3 sposob: globalnaya nastroyka.
        # JSON_AS_ASCII = False => ensure_ascii=False dlya jsonify/response_class.
        if getattr(app, "config", None) is not None:
            app.config["JSON_AS_ASCII"] = False
            changed = True
    except Exception as e:  # pragma: no cover - chisto strakhovka
        return {"ok": False, "mode": "B", "changed": False, "error": str(e)}

    return {"ok": True, "mode": "B", "changed": changed}