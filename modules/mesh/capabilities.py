# -*- coding: utf-8 -*-
"""modules/mesh/capabilities.py - obyavlenie sposobnostey uzla i utility Mesh.

Mosty:
- Yavnyy: (Sestry ↔ Raspredelennye zadachi) ukazyvaet, chto etot uzel umeet (CPU/GPU/instrumenty).
- Skrytyy #1: (SelfCatalog ↔ Planirovschik) dannye ispolzuyutsya dlya planirovaniya claim zadach.
- Skrytyy #2: (Backpressure/RBAC ↔ Set) pri pull/submit uchityvayutsya limity i roli.

Zemnoy abzats:
Kak tablichka na masterskoy: “kakie stanki est, skolko ruk, chto mozhno delat” - eto pomogaet chestno delit rabotu.

# c=a+b"""
from __future__ import annotations
import os, json, platform, shutil, socket
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

DB = os.getenv("MESH_DB","data/mesh/tasks.json")
NODE_ID = os.getenv("MESH_NODE_ID","") or socket.gethostname()

def _ensure():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if not os.path.isfile(DB):
        json.dump({"node": {"id": NODE_ID, "tags": [], "tools": []},
                   "tasks": [], "leases": {}, "builds":[]}, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def _load(): _ensure(); return json.load(open(DB,"r",encoding="utf-8"))
def _save(j): json.dump(j, open(DB,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def capabilities()->Dict[str,Any]:
    tools=[]
    for tool in ["ffmpeg","python","git"]:
        path=shutil.which(tool)
        if path: tools.append({"name": tool, "path": path})
    tags=["garage","rag","passport","cron","p2p","selfevo"]
    info={
        "id": NODE_ID,
        "system": {"os": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
        "tools": tools,
        "tags": tags
    }
    j=_load(); j["node"]=info; _save(j)
    return {"ok": True, "node": info}
# c=a+b