# -*- coding: utf-8 -*-
"""tools/smoke_kompat_006.py — proverka dvukh poslednikh padeniy iz boot-loga:
1) forms_routes AssertionError('expected view func if endpoint is not provided.')
2) mem_kg_routes AssertionError('View function mapping is overwriting ... memory_flashback')
Skript sozdaet lokalnyy Flask app i register both modulya.
# c=a+b"""
from __future__ import annotations
import json, sys
from flask import Flask
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def tr(fun):
    try:
        fun()
        return True
    except Exception as e:
        return f"ERR:{e}"

def t_forms():
    app = Flask("t_forms")
    try:
        from ester.routes.forms_routes import register as reg
    except Exception:
        from routes.forms_routes import register as reg  # fallback
    reg(app)
    return True

def t_memkg():
    app = Flask("t_memkg")
    try:
        from ester.routes.mem_kg_routes import register as reg
    except Exception:
        from routes.mem_kg_routes import register as reg
    reg(app)
    keys = list(app.view_functions.keys())
    ok = any("memory_flashback" in k for k in keys) and any(("alias" in k) or ("mem" in k) or ("_" in k) for k in keys)
    return bool(ok)

res = {
    "forms_routes_ok": tr(t_forms),
    "mem_kg_routes_ok": tr(t_memkg),
}

print(json.dumps(res, ensure_ascii=False, indent=2))