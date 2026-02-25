# -*- coding: utf-8 -*-
"""modules/garage/scaffold.py - “garazh”: karkas novykh moduley s register(app), faylovaya pesochnitsa i proverka.

Mosty:
- Yavnyy: (DevOps ↔ Prilozhenie) bystro sozdat drop-in modul bez pravok app.py.
- Skrytyy #1: (AutoDiscover ↔ Avtonomiya) gotovit importiruemyy put i registratsiyu cherez /app/discover.
- Skrytyy #2: (A/B ↔ Bezopasnost) generate primer route s A/B-obertkoy.

Zemnoy abzats:
Eto kak verstak s naborami: nazhal - i u tebya pustaya “korobka” s provodami, kotoruyu mozhno srazu vstraivat.

# c=a+b"""
from __future__ import annotations
import os, json, time, re
from typing import Dict

GARAGE_ROOT=os.getenv("GARAGE_ROOT","garage")
GARAGE_REG=os.getenv("GARAGE_REG","data/garage/registry.json")
OWNER=os.getenv("GARAGE_DEFAULT_OWNER","Ester")

def _ensure():
    os.makedirs(GARAGE_ROOT, exist_ok=True)
    os.makedirs(os.path.dirname(GARAGE_REG), exist_ok=True)
    if not os.path.isfile(GARAGE_REG):
        json.dump({"projects":{}}, open(GARAGE_REG,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(GARAGE_REG,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(GARAGE_REG,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _valid_name(name: str)->bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""))

def create_project(name: str, route_base: str="/garage", owner: str|None=None)->Dict:
    _ensure()
    if not _valid_name(name): return {"ok": False, "error":"invalid_name"}
    proj_dir=os.path.join(GARAGE_ROOT, name)
    mod_pkg=os.path.join(proj_dir, "routes")
    os.makedirs(mod_pkg, exist_ok=True)
    init=os.path.join(mod_pkg, "__init__.py")
    if not os.path.isfile(init): open(init,"w",encoding="utf-8").write("# package\n")
    # sgeneriruem fayl routov s A/B
    route_file=os.path.join(mod_pkg, f"{name}_routes.py")
    if not os.path.isfile(route_file):
        open(route_file,"w",encoding="utf-8").write(f'''# -*- coding: utf-8 -*-
"""
{GARAGE_ROOT}/{name}/routes/{name}_routes.py — shablonnyy modul.
"""
from __future__ import annotations
from flask import Blueprint, jsonify
from modules.safety.abslot import choose
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp=Blueprint("{name}_routes", __name__)

def _pong_a():
    return {{"ok": True, "slot":"A", "msg":"hello from {name}"}}

def _pong_b():
    # alternative implementation (may be experimental)
    return {{"ok": True, "slot":"B", "msg":"hello from {name} (B)"}}

@bp.route("{route_base}/ping", methods=["GET"])
def api_ping():
    fn=choose(_pong_a, _pong_b)
    return jsonify(fn())

def register(app):
    app.register_blueprint(bp)
# c=a+b
''')
    # registratsiya proekta
    j=_load(); P=j.get("projects") or {}
    P[name]={"dir": proj_dir, "module": f"{GARAGE_ROOT}.{name}.routes.{name}_routes", "route_base": route_base, "owner": owner or OWNER, "t": int(time.time())}
    j["projects"]=P; _save(j)
    return {"ok": True, "project": P[name]}

def add_file(name: str, rel_path: str, content: str)->Dict:
    j=_load(); p=(j.get("projects") or {}).get(name)
    if not p: return {"ok": False, "error":"not_found"}
    # Let's limit ourselves to the sandbox of the project
    base=p["dir"]; full=os.path.abspath(os.path.join(base, rel_path.strip("/")))
    if not full.startswith(os.path.abspath(base)):
        return {"ok": False, "error":"path_outside_garage"}
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full,"w",encoding="utf-8").write(content)
    return {"ok": True, "path": full}

def build(name: str)->Dict:
    """“Dry” check: module import + search for decorated routes."""
    import importlib, inspect, re
    j=_load(); p=(j.get("projects") or {}).get(name)
    if not p: return {"ok": False, "error":"not_found"}
    mod=p["module"]
    try:
        m=importlib.import_module(mod)
        src=inspect.getsource(m)
        routes=re.findall(r'@bp\\.route\\(\\s*"(.*?)"', src)
        return {"ok": True, "imported": True, "routes": routes}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def list_projects()->Dict:
    return _load()

# c=a+b