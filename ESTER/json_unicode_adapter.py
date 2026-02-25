"""Ester JSON unicode adapter.

Pozvolyaet upravlyat rezhimom serializatsii JSON dlya HTTP-otvetov Flask.

AB-pereklyuchatel:
- A (po umolchaniyu): povedenie Flask po umolchaniyu (escape ASCII), nichego ne trogaem.
- B: otklyuchaem ASCII-ekranirovanie dlya JSON-otvetov (JSON_AS_ASCII=False),
     chtoby kirillitsa i drugie unicode-simvoly otobrazhalis normalno.

Use:
- app.py pytaetsya importirovat etot modul i vyzvat apply(app).
- Esli adapter nedostupen ili chto-to poshlo ne tak - Ester prodolzhit rabotat v bezopasnom rezhime."""

import os
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_FLAG = "ESTER_JSON_UNICODE_AB"


def apply(app) -> Dict[str, Any]:
    """Apply JSION Unicode settings to the Flask application.

    Returns a dictionary:
      ZZF0Z"""
    try:
        mode = (os.getenv(_FLAG, "A") or "A").strip().upper()
    except Exception:
        # as safe as possible: if there is something strange in the environment, it doesn’t break
        mode = "A"

    if mode != "B":
        # We don't change anything - default behavior.
        return {"ok": True, "mode": "A", "changed": False}

    # Tries to carefully include Unicode in YSON.
    changed = False
    try:
        # Flask 2/3 compatible method: global setting.
        # JSON_AS_ASCII = False => ensure_ascii=False dlya jsonify/response_class.
        if getattr(app, "config", None) is not None:
            app.config["JSON_AS_ASCII"] = False
            changed = True
    except Exception as e:  # pragma: but the carpet is purely insurance
        return {"ok": False, "mode": "B", "changed": False, "error": str(e)}

    return {"ok": True, "mode": "B", "changed": changed}