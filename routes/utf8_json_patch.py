# -*- coding: utf-8 -*-
"""
routes/utf8_json_patch.py - prinuditelnyy UTF-8 na vydache + ne ekranirovat yunikod.

MOSTY:
- (Yavnyy) after_app_request dobavlyaet charset=utf-8 v Content-Type dlya JSON/HTML.
- (Skrytyy #1) Patch JSON-provaydera Flask: ensure_ascii=False => kirillitsa idet «kak est».
- (Skrytyy #2) Fallback dlya starykh Flask: app.config['JSON_AS_ASCII']=False.

ZEMNOY ABZATs:
Na Windows PowerShell, esli server ne ukazhet kodirovku, otvet chasto
dekodiruetsya « ANSI/1251 », otkuda i «Ð­Ñ...». Etot fayl garantiruet
pravilnye zagolovki i serializatsiyu - bez pravok vashego app.py.
"""

from __future__ import annotations
from flask import Blueprint
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("utf8_json_patch", __name__)

def _patch_json_provider(app):
    # Flask >=2.2: provayder JSON cherez klass; myagko pereopredelim dumps()
    try:
        from flask.json.provider import DefaultJSONProvider  # type: ignore

        class Utf8JSON(DefaultJSONProvider):
            def dumps(self, obj, **kwargs):
                # Ne ekranirovat kirillitsu/yunikod
                kwargs.setdefault("ensure_ascii", False)
                # Krasivo ne vklyuchaem (menshe bayt); vklyuchite pri zhelanii:
                # kwargs.setdefault("indent", 2)
                return super().dumps(obj, **kwargs)

            def loads(self, s: str | bytes, **kwargs):
                return super().loads(s, **kwargs)

        app.json = Utf8JSON(app)  # type: ignore[attr-defined]
    except Exception:
        # Starye Flask: prosto otklyuchim ASCII-ekranirovanie
        app.config["JSON_AS_ASCII"] = False

@bp.after_app_request
def _force_utf8(resp):
    # Esli tip JSON - dobavim charset, esli ego net
    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in ctype and "charset=" not in ctype:
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
    # Chasto polezno i dlya HTML/teksta
    if ctype.startswith("text/") and "charset=" not in ctype:
        resp.headers["Content-Type"] = (resp.headers["Content-Type"] + "; charset=utf-8").strip("; ")
    return resp

def register(app):
    # vklyuchaem provayder do lyubykh otvetov
    _patch_json_provider(app)
    # prosto smontirovat blyuprint (marshrutov tut net) - chtoby after_app_request zarabotal
    app.register_blueprint(bp)
    return bp