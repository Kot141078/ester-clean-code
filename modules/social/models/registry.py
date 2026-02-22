# -*- coding: utf-8 -*-
"""
modules/studio/models/registry.py — reestr i selektor modeley media.

Mosty:
- Yavnyy: (Provaydery ↔ Orkestrator) edinyy spisok vozmozhnostey i vybor luchshego pod zadachu.
- Skrytyy #1: (Ekonomika ↔ CostFence) mozhno integrirovat byudzhet v score.
- Skrytyy #2: (Flot ↔ Lokalnost) predpochitaet lokalnye provaydery pri ravnoy otsenke.

Zemnoy abzats:
Kak «rasporyaditel stseny»: znaet, kto iz artistov ryadom i skolko stoit, i stavit na rol podkhodyaschego.

# c=a+b
"""
from __future__ import annotations
import os, json, shutil
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

CFG = os.getenv("MEDIA_MODEL_CFG","data/studio/models.json")

def _load_cfg()->Dict[str,Any]:
    if not os.path.isfile(CFG):
        return {"providers": [], "weights": {"quality":0.7,"latency":0.2,"cost":0.1}}
    return json.load(open(CFG,"r",encoding="utf-8"))

def _have_cmd(cmd: str)->bool:
    # grubaya proverka nalichiya komandy
    parts=cmd.split(" ",1)
    return bool(shutil.which(parts[0]))

def list_providers()->List[Dict[str,Any]]:
    cfg=_load_cfg()
    out=[]
    for p in cfg.get("providers",[]):
        ok=True
        if p.get("kind")=="local-cli":
            avail=p.get("available_if") or p.get("bin_env")
            if avail:
                ok = _have_cmd(avail.split()[0])
        if p.get("kind")=="http":
            env=p.get("env_key","")
            ok = bool(os.getenv(env,"").strip())
        p2=dict(p); p2["available"]=bool(ok)
        out.append(p2)
    return out

def select(task: str, prefer_local: bool=True)->Dict[str,Any]:
    """
    Vozvraschaet luchshego dostupnogo provaydera po score.
    """
    cfg=_load_cfg()
    ws=cfg.get("weights",{"quality":0.6,"latency":0.2,"cost":0.2})
    best=None; best_score=-1e9
    for p in list_providers():
        if not p.get("available"): continue
        if p.get("task")!=task: continue
        # lokalnye legche na +0.05
        local_bonus = 0.05 if (prefer_local and p.get("kind")=="local-cli") else 0.0
        score = p.get("quality",0)*ws.get("quality",0.6) - p.get("latency",0)*ws.get("latency",0.2) - p.get("cost",0)*ws.get("cost",0.2) + local_bonus
        if score>best_score:
            best=p; best_score=score
    return best or {}
# c=a+b