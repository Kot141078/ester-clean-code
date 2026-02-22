
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
modules.graph.kg_http — HTTP‑router eksporta KG (bez avtopodklyucheniya).
Mosty:
- Yavnyy: register_fastapi/register_flask pod prefiksom `/compat/kg` (ENV `ESTER_KG_PREFIX`).
- Skrytyy #1: (DX ↔ Sovmestimost) — JSON snapshot iz kg_export.snapshot() bez pobochek.
- Skrytyy #2: (Kachestvo ↔ Integratsii) — gotovo dlya vstraivaniya v lyubuyu adminku.

Zemnoy abzats:
Otdaem «srez grafa» po HTTP, chtoby storonnie paneli/skripty mogli nablyudat i testirovat sistemu.
# c=a+b
"""
import os, json
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
_PREFIX = os.getenv("ESTER_KG_PREFIX", "/compat/kg")

def _snap_json() -> str:
    from modules.graph.kg_export import snapshot
    return json.dumps(snapshot(), ensure_ascii=False, indent=2)

# FastAPI
def register_fastapi(app, prefix: Optional[str]=None) -> bool:
    try:
        from fastapi import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/ping")
    def _ping():
        return {"ok": True, "mod": "graph.kg_http"}
    @app.get(prefix + "/snapshot.json", response_class=__import__("fastapi").Response)  # type: ignore
    def _snap():
        return Response(content=_snap_json(), media_type="application/json")
    return True

# Flask
def register_flask(app, prefix: Optional[str]=None) -> bool:
    try:
        from flask import Response
    except Exception:
        return False
    prefix = prefix or _PREFIX
    @app.get(prefix + "/ping")
    def _ping():
        return {"ok": True, "mod": "graph.kg_http"}
    @app.get(prefix + "/snapshot.json")
    def _snap():
        return Response(_snap_json(), mimetype="application/json")
    return True