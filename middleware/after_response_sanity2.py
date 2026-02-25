
# -*- coding: utf-8 -*-
from __future__ import annotations
import os, io
from flask import make_response
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_AB = os.getenv("ESTER_AFTER_SANITY2_AB", "B").upper()

def _try_log(msg):
    try:
        os.makedirs("data", exist_ok=True)
        with io.open("data/bringup_after_chain.log", "a", encoding="utf-8") as f:
            f.write(u"[AfterSanity2] %s\n" % msg)
    except Exception:
        pass

def _sanity(resp):
    if resp is None:
        _try_log("normalized None -> 204")
        r = make_response("", 204)
        r.headers["X-Ester-AfterSanity2"] = "fixed"
        return r
    try:
        # All Responses have headings - put a marker in any case
        resp.headers["X-Ester-AfterSanity2"] = resp.headers.get("X-Ester-AfterSanity2", "ok")
    except Exception:
        # Just in case
        r = make_response("", 204)
        r.headers["X-Ester-AfterSanity2"] = "fallback"
        return r
    return resp

def register(app):
    if _AB == "B":
        app.after_request(_sanity)