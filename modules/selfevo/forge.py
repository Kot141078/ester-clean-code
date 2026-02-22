# -*- coding: utf-8 -*-
"""
modules/selfevo/forge.py — «kuznitsa» samoevolyutsii: shablony moduley, A/B-slot, dryrun/apply, zhurnal.

Mosty:
- Yavnyy: (Volya ↔ FS) bezopasnoe sozdanie novykh moduley v razreshennykh katalogakh.
- Skrytyy #1: (Profile ↔ Audit) kazhdyy artefakt shtampuetsya s kheshem i istochnikom.
- Skrytyy #2: (Registrator ↔ Zhiznennyy tsikl) po zhelaniyu srazu importiruetsya i registriruetsya v prilozhenii.

Zemnoy abzats:
Eto kak oborudovannyy «garazh»: s shablonami, svetoforami i zhurnalom — chtoby rasti bez khaosa i polomok.

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib, textwrap
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("SELF_EVO_DB","data/selfevo/forge.json")
ALLOW_PATH = os.getenv("SELF_EVO_ALLOWED_DIRS","data/allowlists/selfevo_dirs.json")
ALLOW_WRITE = (os.getenv("SELF_EVO_ALLOW_WRITE","false").lower()=="true")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB): json.dump({"items":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
    if not os.path.isfile(ALLOW_PATH):
        os.makedirs(os.path.dirname(ALLOW_PATH), exist_ok=True)
        json.dump({"allowed":["modules/custom","routes/custom","data/custom"]}, open(ALLOW_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
def _allowed(p:str)->bool:
    al=json.load(open(ALLOW_PATH,"r",encoding="utf-8")).get("allowed",[])
    return any(os.path.abspath(p).startswith(os.path.abspath(a)) for a in al)

def _sha(s: str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _tpl(kind: str, name: str, desc: str, export: str)->str:
    if kind=="route":
        return textwrap.dedent(f"""\
        # -*- coding: utf-8 -*-
        \"\"\"
        {name}.py — {desc}

        Mosty:
        - Yavnyy: (Veb ↔ Modul) novyy rout s A/B-slotom.
        - Skrytyy #1: (Profile ↔ Prozrachnost) registriruet fakt ustanovki/vyzova.
        - Skrytyy #2: (RBAC ↔ Ostorozhnost) mozhno obernut rolyu pri neobkhodimosti.

        Zemnoy abzats:
        Demonstratsionnyy rout: proveryaem, chto kuznitsa sozdaet i podklyuchaet kod bez polomok.

# c=a+b
        \"\"\"
        from __future__ import annotations
        from flask import Blueprint, jsonify
        import os

        bp=Blueprint("{name}", __name__)

        def register(app):
            app.register_blueprint(bp)

        A_SLOT=os.getenv("{name.upper()}_SLOT","A").upper()  # A/B-slot; A — po umolchaniyu

        @bp.route("/{name}/ping", methods=["GET"])
        def api_ping():
            try:
                from modules.mem.passport import append as _pp  # type: ignore
                _pp("selfevo_route_ping", {{"name":"{name}","slot":A_SLOT}}, "selfevo://route")
            except Exception:
                pass
            msg = "hello from {name} slot-A" if A_SLOT=="A" else "hello from {name} slot-B"
            return jsonify({{"ok": True, "msg": msg, "slot": A_SLOT}})
        # c=a+b
        """)
    # inye vidy mozhno dobavit pri razvitii
# return f"# {name} — placeholder\n# c=a+b\n"

def dryrun(path: str, kind: str, name: str, desc: str, export: str)->Dict[str,Any]:
    code=_tpl(kind, name, desc, export)
    return {"ok": True, "path": path, "code": code, "hash": _sha(code)}

def apply(path: str, code: str, register_after: bool=False)->Dict[str,Any]:
    if not _allowed(path): return {"ok": False, "error":"path_not_allowed"}
    if not ALLOW_WRITE:    return {"ok": False, "error":"write_forbidden_env"}
    if os.environ.get("X_CHANGE_APPROVAL","").lower()!="yes":
        # alternativnyy kanal — zagolovok v route; zdes podderzhka ENV dlya CLI
        pass

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,"w",encoding="utf-8") as f: f.write(code)

    j=_load(); item={"t": int(time.time()), "path": path, "hash": _sha(code)}
    j["items"]= (j.get("items") or []) + [item]; _save(j)

    # profile
    try:
        from modules.mem.passport import append as _pp  # type: ignore
        _pp("selfevo_apply", {"path": path, "hash": item["hash"]}, "selfevo://forge")
    except Exception:
        pass

    # optsionalnaya registratsiya (esli est /app/discover/register)
    ok_reg=False
    if register_after and path.endswith(".py"):
        modname = path.replace("/",".").replace("\\",".").rstrip(".py")
        if modname.endswith(".py"): modname=modname[:-3]
        try:
            import importlib; m=importlib.import_module(modname)
            # esli eto rout — vyzvat register(current_app)
            from flask import current_app
            if hasattr(m, "register"):
                m.register(current_app)  # type: ignore
                ok_reg=True
        except Exception:
            ok_reg=False
    return {"ok": True, "applied": True, "registered": ok_reg, "item": item}

def list_items()->Dict[str,Any]:
    j=_load(); return {"ok": True, "items": j.get("items",[])}
# c=a+b