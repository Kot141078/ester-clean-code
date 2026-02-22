# -*- coding: utf-8 -*-
"""
modules/kg/shadow.py — tenevoy graf znaniy (uzly/svyazi) dlya avtolinka.

Mosty:
- Yavnyy: (KG ↔ Memory) sozdaet/obnovlyaet uzly i svyazi «upominanie→suschnost».
- Skrytyy #1: (Gipotezy ↔ Uzly) gipotezam udobno ssylatsya na id uzlov.
- Skrytyy #2: (RAG ↔ Relevantnost) normalizovannye uzly uluchshayut retriv.

Zemnoy abzats:
Mini-«vikipediya» vnutri: spisok suschnostey (lyudi/organizatsii/mesta/tekhnologii) i gde oni upominalis.

# c=a+b
"""
from __future__ import annotations
import os, json, time, hashlib
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB=os.getenv("KG_SHADOW_DB","data/kg/shadow.json")

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"nodes":{}, "links":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _node_id(kind: str, name: str)->str:
    h=hashlib.sha1(f"{kind}:{name}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{name}:{h}"

def ensure_node(kind: str, name: str, aliases: List[str]|None=None)->Dict[str,Any]:
    j=_load(); nid=_node_id(kind, name)
    node=j["nodes"].get(nid) or {"id": nid, "kind": kind, "name": name, "aliases": list(aliases or []), "created": int(time.time())}
    j["nodes"][nid]=node; _save(j)
    return {"ok": True, "node": node}

def link_memory(mem_id: str, node_id: str)->Dict[str,Any]:
    j=_load()
    j["links"].append({"t": int(time.time()), "mem_id": mem_id, "node_id": node_id})
    _save(j)
    return {"ok": True}

def stats()->Dict[str,Any]:
    j=_load(); return {"ok": True, "nodes": len(j.get("nodes",{})), "links": len(j.get("links",[]))}
# c=a+b