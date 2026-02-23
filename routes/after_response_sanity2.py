# -*- coding: utf-8 -*-
from __future__ import annotations
import os, datetime
from flask import Response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

AB = os.getenv("ESTER_AFTER_SANITY2_AB", "B").upper()

def _log(msg: str) -> None:
    try:
        base = os.getenv("ESTER_DATA_ROOT", "data")
        os.makedirs(base, exist_ok=True)
        p = os.path.join(base, "bringup_after_chain.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

def register(app):
    if AB != "B":
        _log("after_response_sanity2: skipped (AB!=B)")
        return

    @app.after_request
    def _ensure_response(resp):
        # Esli kakoy-to obrabotchik vernul None - normalizuem v 204
        if resp is None:
            _log("after_response_sanity2: resp=None -> 204")
            return Response(status=204)
        return resp

    _log("after_response_sanity2: installed")