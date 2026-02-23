# -*- coding: utf-8 -*-
import sys, pathlib
sys.path.insert(0, r"D:\ester-project")
from flask import Flask
from ESTER.routes.a00_ep_shim import register
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
app = Flask("diag")
print("CLASS BEFORE:", hasattr(app.__class__.add_url_rule, "__ester_ep_shim__"))
print("register:", register(app))
print("CLASS  AFTER:", hasattr(app.__class__.add_url_rule, "__ester_ep_shim__"))
def h(): return "hi"
app.add_url_rule("/a", endpoint="same", view_func=h)
app.add_url_rule("/b", endpoint="same", view_func=h)
eps = sorted([k for k in app.view_functions if k.startswith("same")])
print("EPS:", eps)
print("uniq_ok:", ("same" in eps) and any(k.startswith("same__") for k in eps))