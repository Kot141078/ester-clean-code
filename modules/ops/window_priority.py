# -*- coding: utf-8 -*-
"""modules/ops/window_priority.py - priority okon "play".

Khranilische: data/desktop/window_priority.json
Funktsii:
- get_list() -> [{"title":"...","priority":10}, ...]
- save_list(items)
- pick_focus(): vybiraet dostupnoe okno po ubyvaniyu prioriteta i fokusiruet.

MOSTY:
- Yavnyy: (Igra ↔ Control) Ester znaet, kakoe okno “glavnoe” seychas.
- Skrytyy #1: (Kibernetika ↔ Nadezhnost) menshe promakhov klikom “ne v to okno”.
- Skrytyy #2: (Inzheneriya ↔ Psikhologiya) priorityt kak “vnimanie” igroka.

ZEMNOY ABZATs:
Simple JSON, offline. Rabotaet poverkh uzhe realizovannykh operatsiy okon.

# c=a+b"""
from __future__ import annotations
import os, json
from typing import List, Dict, Any

from modules.ops.window_ops import list_windows, focus_by_title
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
PATH = os.path.join(ROOT, "data", "desktop")
FILE = os.path.join(PATH, "window_priority.json")

def _ensure():
    os.makedirs(PATH, exist_ok=True)
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"items":[]}, f, ensure_ascii=False, indent=2)

def get_list() -> List[Dict[str, Any]]:
    _ensure()
    with open(FILE, "r", encoding="utf-8") as f:
        return (json.load(f) or {}).get("items", [])

def save_list(items: List[Dict[str, Any]]) -> None:
    _ensure()
    items2 = sorted([{ "title": str(i.get("title","")), "priority": int(i.get("priority",0)) } for i in items], key=lambda x: -x["priority"])
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump({"items": items2}, f, ensure_ascii=False, indent=2)

def pick_focus() -> Dict[str, Any]:
    items = get_list()
    if not items:
        return {"ok": False, "error": "empty_priority"}
    ws = list_windows()
    names = [w["title"].lower() for w in ws]
    for it in items:
        t = it["title"].lower()
        if any(t in name for name in names):
            # fokus po chasti zagolovka
            wid = focus_by_title(it["title"])
            return {"ok": bool(wid), "title": it["title"]}
    return {"ok": False, "error": "no_window_found"}