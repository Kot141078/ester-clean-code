# -*- coding: utf-8 -*-
"""
modules/security/safe_windows.py — chernyy spisok okon/prilozheniy (safe-okna).

Funktsii:
- set_policy(deny:list[str], allow:list[str]) — podstrochnye filtry zagolovkov; allow imeet prioritet.
- is_safe(title:str) -> bool — mozhno li deystvovat (True — mozhno, False — zablokirovano).
- guard_call(kind, title, payload) -> {ok|skipped} — vrapper dlya RPA-zovov.

Khranilische: data/security/safe_windows.json

Integratsiya:
- Vyzovy khotkeev/miksov/vorkflou mogut proveryat is_safe(title) pered otpravkoy.
- Dobavlyaem REST-ruchki v routes/safe_windows_routes.py.

MOSTY:
- Yavnyy: (Bezopasnost ↔ Kontrol) zapret deystviy v chuvstvitelnykh oknakh.
- Skrytyy #1: (Logika ↔ Ekspluatatsiya) prostye pravila: deny/allow.
- Skrytyy #2: (Memory ↔ UX) odna nastroyka — zaschita vsego kontura.

ZEMNOY ABZATs:
Prostoy JSON, podstrochnoe sravnenie zagolovka, bez SDK prilozheniy.

# c=a+b
"""
from __future__ import annotations
import os, json
from typing import Dict, Any, List
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOT = os.environ.get("ESTER_ROOT", os.getcwd())
DIR  = os.path.join(ROOT, "data", "security")
os.makedirs(DIR, exist_ok=True)
FILE = os.path.join(DIR, "safe_windows.json")

_DEF = {"deny": [], "allow": []}

def _load() -> Dict[str, Any]:
    if not os.path.exists(FILE):
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(_DEF, f, ensure_ascii=False, indent=2)
    with open(FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(obj: Dict[str, Any]) -> None:
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def set_policy(deny: List[str], allow: List[str]) -> Dict[str, Any]:
    obj = {"deny": list(deny or []), "allow": list(allow or [])}
    _save(obj); return {"ok": True, **obj}

def is_safe(title: str) -> bool:
    obj = _load(); t = (title or "").lower()
    for a in obj.get("allow", []):
        if a.lower() in t:
            return True
    for d in obj.get("deny", []):
        if d.lower() in t:
            return False
    return True

def guard_call(kind: str, title: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not is_safe(title):
        return {"ok": True, "skipped": True, "safe": True, "kind": kind, "title": title}
    return {"ok": True, "skipped": False}