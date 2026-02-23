import sys
sys.path.insert(0, r"D:\ester-project")
from flask import Flask
from ESTER.routes.a00_ep_shim import register
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

app = Flask("y")
register(app)

def h(): 
    return "hi"

app.add_url_rule("/a", endpoint="same", view_func=h)
app.add_url_rule("/b", endpoint="same", view_func=h)

eps = sorted([k for k in app.view_functions.keys() if k.startswith("same")])
print("EPS:", eps)
print("uniq_ok:", any(e == "same" for e in eps) and any(e.startswith("same__") for e in eps))