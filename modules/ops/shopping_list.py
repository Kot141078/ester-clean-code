# -*- coding: utf-8 -*-
"""modules/ops/shopping_list.py - spisok pokupok i zadaniya "Pape"/operatoru.

Mosty:
- Yavnyy: (Operatsii ↔ Ekonomika) kazhdaya pokupka mozhet byt uvyazana s rezervom/spisaniem.
- Skrytyy #1: (Search ↔ Praktika) pri neobkhodimosti podskazyvaem postavschikov cherez web_search (snaruzhi).
- Skrytyy #2: (Kibernetika ↔ Kontrol) zadaniya fiksiruyutsya i zakryvayutsya cherez REST.

Zemnoy abzats:
This check-list v magazin: what kupit, skolko stoit, where otchitatsya.

# c=a+b"""
from __future__ import annotations
import json, os, time, uuid
from typing import Any, Dict, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ASSIGN_PATH = os.getenv("OPS_ASSIGN_PATH","data/ops/assignments.json")

def _load() -> Dict[str, Any]:
    try:
        return json.load(open(ASSIGN_PATH,"r",encoding="utf-8"))
    except Exception:
        return {"tasks": []}

def _save(st: Dict[str, Any]):
    os.makedirs(os.path.dirname(ASSIGN_PATH), exist_ok=True)
    json.dump(st, open(ASSIGN_PATH,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

def add_assignments(items: List[Dict[str,Any]], assign_to: str = "papa") -> Dict[str, Any]:
    st = _load()
    created = []
    for it in items or []:
        tid = str(uuid.uuid4())
        st["tasks"].append({
            "id": tid, "who": assign_to, "type": "buy",
            "title": f"Kupit: {it.get('name')} x{it.get('qty',1)}",
            "budget": float(it.get("budget") or 0),
            "status": "open", "ts": int(time.time()), "meta": {"tags": it.get("tags", [])}
        })
        created.append(tid)
    _save(st)
    return {"ok": True, "created": created}

def list_assignments() -> Dict[str, Any]:
    return {"ok": True, **_load()}

def complete_assignment(task_id: str) -> Dict[str, Any]:
    st = _load()
    for t in st["tasks"]:
        if t["id"] == task_id:
            t["status"] = "done"; t["done_ts"] = int(time.time())
            _save(st); return {"ok": True}
    return {"ok": False, "error":"not found"}