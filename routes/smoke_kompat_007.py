# -*- coding: utf-8 -*-
"""
tools/smoke_kompat_007.py — proverka shim-a endpoint-ov (universalnyy zapusk)
# c=a+b
"""
from __future__ import annotations
import json, os, sys, pathlib
_THIS = pathlib.Path(__file__).resolve()
_ROOT = _THIS.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask
try:
    from ESTER.routes.a00_ep_shim import register  # type: ignore
except Exception:
    from ester.routes.a00_ep_shim import register  # type: ignore

def tr(fn):
    try:
        return bool(fn())
    except Exception as e:
        return f"ERR:{e}"

def t_no_view():
    app = Flask("x")
    register(app)
    app.add_url_rule("/bad", endpoint="bad", view_func=None)
    return True

def t_unique():
    app = Flask("y")
    register(app)
    def hello():
        return "hi"
    app.add_url_rule("/a", endpoint="same", view_func=hello)
    app.add_url_rule("/b", endpoint="same", view_func=hello)
    eps = list(app.view_functions.keys())
    return any(e == "same" for e in eps) and any(e.startswith("same__") for e in eps)

print(json.dumps({"no_view_ok": tr(t_no_view), "uniq_ok": tr(t_unique)}, ensure_ascii=False, indent=2))
