# -*- coding: utf-8 -*-
from __future__ import annotations

"""
Hook-most: v tvoey sborke direktoriya ESTER/hooks zagruzhaetsya pri starte
i dlya kazhdogo modulya vyzyvaetsya init_app(app). Zdes my prinuditelno
importiruem routes.jwt_glue_routes i registriruem ego Blueprint.
"""

from typing import Any
from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def init_app(app: Flask) -> None:  # vyzyvaetsya freymvorkom
    try:
        from routes import jwt_glue_routes as m  # import po kornevomu paketu
    except Exception:
        try:
            # zapasnoy put (esli lezhit v ESTER.jwt_glue_routes)
            from ESTER import jwt_glue_routes as m  # type: ignore
        except Exception:
            return

    # 1) esli est bp — registriruem
    bp = getattr(m, "bp", None)
    if bp is not None:
        try:
            if "jwt_glue" not in getattr(app, "blueprints", {}):
                app.register_blueprint(bp)  # bezopasno: vtoroy raz ne zaregistriruetsya
        except Exception:
            pass

    # 2) na vsyakiy — dergaem vozmozhnye fabriki
    for name in ("init_app", "register", "setup", "register_app"):
        fn = getattr(m, name, None)
        if callable(fn):
            try:
                fn(app)  # type: ignore[call-arg]
            except Exception:
                pass