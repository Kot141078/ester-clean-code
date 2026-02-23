# routes/utf8_json_routes.py
from __future__ import annotations

import os
import json
from flask import Flask, Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Slot A: minimalno i bezopasno -----------------------------------------
def _register_slot_a(app: Flask) -> None:
    # Otklyuchaem ASCII-ekranirovanie dlya jsonify
    app.config.setdefault("JSON_AS_ASCII", False)

    @app.after_request
    def _ensure_charset_a(resp: Response) -> Response:
        ctype = resp.headers.get("Content-Type", "")
        if ctype and "charset=" not in ctype:
            if ctype.startswith("application/json") or ctype.startswith("text/"):
                resp.headers["Content-Type"] = f"{ctype}; charset=utf-8"
        return resp


# --- Slot B: kastomnyy provayder JSON (rasshirennyy) --------------------------
class UTF8JSONProvider(Flask.json_provider_class):
    def dumps(self, obj, *, option=None, **kwargs):
        kwargs.setdefault("ensure_ascii", False)
        kwargs.setdefault("sort_keys", False)
        kwargs.setdefault("separators", (",", ":"))
        return json.dumps(obj, **kwargs)

    def loads(self, s: str | bytes, **kwargs):
        return json.loads(s, **kwargs)


def _register_slot_b(app: Flask) -> None:
    app.config.setdefault("JSON_AS_ASCII", False)
    # Sovmestimost s raznymi versiyami Flask
    try:
        app.json_provider_class = UTF8JSONProvider  # type: ignore[attr-defined]
        app.json = app.json_provider_class(app)      # type: ignore[attr-defined]
    except Exception:
        app.json = UTF8JSONProvider(app)            # fallback

    @app.after_request
    def _ensure_charset_b(resp: Response) -> Response:
        ctype = resp.headers.get("Content-Type", "")
        if ctype and "charset=" not in ctype:
            if ctype.startswith("application/json") or ctype.startswith("text/"):
                resp.headers["Content-Type"] = f"{ctype}; charset=utf-8"
        return resp


# --- Tochka vkhoda avtozagruzchika ----------------------------------------------
def register(app: Flask) -> None:
    """
    Vyzyvaetsya avtopodklyuchatelem routov. Slot vybiraetsya peremennoy
    okruzheniya ESTER_JSON_SLOT: 'A' (po umolchaniyu) ili 'B'.
    """
    slot = os.getenv("ESTER_JSON_SLOT", "A").upper().strip()
    if slot == "B":
        _register_slot_b(app)
        try:
            app.logger.info("utf8_json_routes: slot B (custom JSON provider) enabled")
        except Exception:
            pass
    else:
        _register_slot_a(app)
        try:
            app.logger.info("utf8_json_routes: slot A (JSON_AS_ASCII=False) enabled")
        except Exception:
            pass