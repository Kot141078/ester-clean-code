# -*- coding: utf-8 -*-
from __future__ import annotations
import json, sys, pathlib, importlib.util

_THIS = pathlib.Path(__file__).resolve()
_ROOT = _THIS.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from flask import Flask
from ESTER.routes.a00_ep_shim import register
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

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

    def hello1():
        return "hi1"

    def hello2():
        return "hi2"

    app.add_url_rule("/a", endpoint="same", view_func=hello1)
    app.add_url_rule("/b", endpoint="same", view_func=hello2)  # DRUGAYa funktsiya → dolzhna srabotat unikalizatsiya

    eps = list(app.view_functions.keys())
    return ("same" in eps) and any(k.startswith("same__") for k in eps)

print(json.dumps(
    {"no_view_ok": tr(t_no_view), "uniq_ok": tr(t_unique)},
    ensure_ascii=False, indent=2
))