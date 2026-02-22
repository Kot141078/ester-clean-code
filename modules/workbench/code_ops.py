# -*- coding: utf-8 -*-
"""
modules/workbench/code_ops.py — bezopasnaya masterskaya koda (skeffolding/zapis/listing).

Mosty:
- Yavnyy: (Volya ↔ Kod) Ester sozdaet novye fayly i moduli pod kontrolem pravil.
- Skrytyy #1: (AutoDiscover ↔ Rasshiryaemost) srazu stykuetsya s dinamicheskoy registratsiey.
- Skrytyy #2: (Bezopasnost ↔ RBAC) zapis dostupna tolko admin, s bekapom i kheshom.

Zemnoy abzats:
Eto kak «garazh s instrumentami»: shablony, akkuratnaya zapis s rezervnoy kopiey i spisok togo, chem uzhe vladeem.

# c=a+b
"""
from __future__ import annotations
import os, time, json, hashlib
from typing import Any, Dict, List

ROOT   = os.getenv("WORKBENCH_ROOT",".")
ALLOW  = [x.strip() for x in (os.getenv("WORKBENCH_ALLOW_PKGS","routes.,modules.") or "").split(",") if x.strip()]
STAGE  = os.getenv("WORKBENCH_STAGE","data/workbench/stage")

def _ensure():
    os.makedirs(STAGE, exist_ok=True)

def _allowed_package(pkg: str)->bool:
    return any(pkg.startswith(p) for p in ALLOW)

def _hash(b: bytes)->str:
    return hashlib.sha256(b).hexdigest()

ROUTE_TEMPLATE = """# -*- coding: utf-8 -*-
\"\"\"
{name}.py — shablonnyy route.

Mosty:
- Yavnyy: (Veb ↔ Modul) bazovyy endpoint s markerami kachestva.
- Skrytyy #1: (Profile ↔ Memory) gotov k dorabotke logirovaniya.
- Skrytyy #2: (AutoDiscover ↔ Rasshirenie) etomu faylu ne nuzhno pravit app.py.

Zemnoy abzats:
Startovaya tochka: prostoy endpoint dlya proverki tsepochki «skeffolding→registratsiya→vyzov».

# c=a+b
\"\"\"
from __future__ import annotations
from flask import Blueprint, jsonify

bp = Blueprint("{short}", __name__)

def register(app):
    app.register_blueprint(bp)

@bp.route("/sample/hello", methods=["GET"])
def sample_hello():
    return jsonify({{"ok": True, "hello": "{short}"}})
# c=a+b
"""

MODULE_TEMPLATE = '''# -*- coding: utf-8 -*-
"""
{ name }.py — shablonnyy modul.

Mosty:
- Yavnyy: (Modul ↔ Ostalnoy kod) minimalnaya zagotovka.
- Skrytyy #1: (Profile ↔ Memory) mesto pod log.
- Skrytyy #2: (AutoDiscover ↔ Rasshirenie) komponuetsya svobodno.

Zemnoy abzats:
Chistyy list pod novuyu logiku. Akkuratnaya strukturnaya osnova.

# c=a+b
"""
from __future__ import annotations
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def ping()->dict:
    return {"ok": True, "pong": "{ short }"}
# c=a+b
'''

def scaffold(kind: str, package: str, name: str)->Dict[str,Any]:
    """
    kind: 'route'|'module', package: 'routes.sample_hello' | 'modules.foo.bar'
    """
    _ensure()
    if not _allowed_package(package):
        return {"ok": False, "error":"not_allowed_package"}
    rel = package.replace(".", "/") + ".py"
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    short = name.strip().replace(".","_")
    body = (ROUTE_TEMPLATE if kind=="route" else MODULE_TEMPLATE).format(name=package, short=short)
    if os.path.exists(path):
        # ne peretirat — pishem ryadom .new
        path_new = path + ".new"
        open(path_new, "w", encoding="utf-8").write(body)
        return {"ok": True, "path": path_new, "note":"exists, wrote .new"}
    open(path, "w", encoding="utf-8").write(body)
    return {"ok": True, "path": path}

def write_file(path: str, content: str, mode: str="overwrite")->Dict[str,Any]:
    """
    Bezopasnaya zapis: cherez staging + bekap pri overwrite.
    """
    _ensure()
    if ".." in path or not any(path.replace("\\","/").startswith(p.replace(".","/")) for p in [a[:-1] for a in ALLOW]):
        return {"ok": False, "error":"path_not_allowed"}
    abspath = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    data = content.encode("utf-8")
    h = _hash(data)
    stage = os.path.join(STAGE, f"{int(time.time())}_{h}.tmp")
    open(stage,"wb").write(data)
    if mode=="append" and os.path.exists(abspath):
        with open(abspath,"ab") as f: f.write(data)
    else:
        if os.path.exists(abspath):
            backup = f"{abspath}.bak.{int(time.time())}"
            with open(abspath,"rb") as f: open(backup,"wb").write(f.read())
        with open(abspath,"wb") as f: f.write(data)
    return {"ok": True, "path": abspath, "sha256": h}

def list_files()->Dict[str,Any]:
    files=[]
    for prefix in ["routes","modules"]:
        base=os.path.join(ROOT, prefix)
        if not os.path.isdir(base): continue
        for dirpath, _, names in os.walk(base):
            for n in names:
                if n.endswith(".py"):
                    rel=os.path.join(dirpath,n).replace(ROOT+"/","")
                    files.append(rel)
    return {"ok": True, "items": sorted(files)}
# c=a+b